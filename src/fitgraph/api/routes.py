"""API route handlers for the FitGraph inference service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from fitgraph.api.schemas import (
    CatalogItem,
    CatalogItemOut,
    CatalogItemsResponse,
    CatalogSearchResponse,
    CategoryCount,
    CategoryListResponse,
    CompatibilityRequest,
    CompatibilityResponse,
    CreateOutfitRequest,
    DeleteOutfitResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    OutfitHistoryEntry,
    OutfitHistoryResponse,
    OutfitResponse,
    OutfitSuggestionItem,
    OutfitSuggestionsResponse,
)
from fitgraph.api.serving import ModelService, get_model_service
from fitgraph.db.models import Item, ItemEmbedding, Outfit, OutfitItem, Rating
from fitgraph.db.queries import (
    list_categories,
    list_items_by_category,
    search_items_by_tag,
    user_outfit_history,
)
from fitgraph.db.session import get_engine, get_session

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------


def _get_db() -> Session:  # type: ignore[return]
    """Yield a database session; close it afterwards."""
    try:
        engine = get_engine()
        factory = get_session(engine)
        session: Session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


DBSession = Annotated[Session, Depends(_get_db)]


# ---------------------------------------------------------------------------
# Model service dependency
# ---------------------------------------------------------------------------


def _get_svc() -> ModelService:
    return get_model_service()


SvcDep = Annotated[ModelService, Depends(_get_svc)]


def _require_model(svc: ModelService) -> ModelService:
    """Raise 503 if the model is not loaded."""
    if not svc.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. No valid checkpoint found.",
        )
    return svc


# ---------------------------------------------------------------------------
# GET /healthz
# ---------------------------------------------------------------------------


@router.get("/healthz", response_model=HealthResponse)
def healthz(svc: SvcDep) -> HealthResponse:
    """Return service health and current model version."""
    from fitgraph.api.main import get_p99_latency_ms  # noqa: PLC0415

    return HealthResponse(
        status="ok",
        model_version=svc.current_version,
        p99_latency_ms=get_p99_latency_ms(),
    )


# ---------------------------------------------------------------------------
# POST /compatibility
# ---------------------------------------------------------------------------


@router.post("/compatibility", response_model=CompatibilityResponse)
def compatibility(
    body: CompatibilityRequest,
    svc: SvcDep,
    db: DBSession,
) -> CompatibilityResponse:
    """Return the type-aware compatibility score between two catalog items."""
    _require_model(svc)

    def _get_embedding_and_type(item_id: str) -> tuple[np.ndarray, str]:
        item = db.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")
        ie = db.get(ItemEmbedding, item_id)
        if ie is None or ie.embedding is None:
            raise HTTPException(
                status_code=404, detail=f"Embedding not found for item: {item_id}"
            )
        emb = np.array(ie.embedding, dtype=np.float32)
        cat = item.semantic_category or ""
        return emb, cat

    emb_a, type_a = _get_embedding_and_type(body.item_id_a)
    emb_b, type_b = _get_embedding_and_type(body.item_id_b)
    score = svc.score(emb_a, type_a, emb_b, type_b)
    return CompatibilityResponse(score=score)


# ---------------------------------------------------------------------------
# POST /outfits
# ---------------------------------------------------------------------------


@router.post("/outfits", response_model=OutfitResponse, status_code=201)
def create_outfit(body: CreateOutfitRequest, db: DBSession) -> OutfitResponse:
    """Create a new outfit and associate item IDs with it."""
    outfit = Outfit(user_id=body.user_id, name=body.name)
    db.add(outfit)
    db.flush()

    for position, item_id in enumerate(body.item_ids):
        db.add(OutfitItem(outfit_id=outfit.id, item_id=item_id, position=position))
    db.flush()

    return OutfitResponse(
        outfit_id=outfit.id,
        user_id=outfit.user_id,
        name=outfit.name,
        item_ids=body.item_ids,
    )


# ---------------------------------------------------------------------------
# GET /outfits
# ---------------------------------------------------------------------------


@router.get("/outfits", response_model=OutfitHistoryResponse)
def get_outfits(
    db: DBSession,
    user_id: int = Query(..., description="User ID to look up outfits for"),
) -> OutfitHistoryResponse:
    """Return the outfit history for a user."""
    history = user_outfit_history(db, user_id)
    entries = [
        OutfitHistoryEntry(
            outfit_id=entry["outfit_id"],
            outfit_name=entry["outfit_name"],
            created_at=entry["created_at"].isoformat() if entry["created_at"] else None,
            item_ids=[it.id for it in entry["items"]],
        )
        for entry in history
    ]
    return OutfitHistoryResponse(outfits=entries)


# ---------------------------------------------------------------------------
# DELETE /outfits/{outfit_id}
# ---------------------------------------------------------------------------


@router.delete("/outfits/{outfit_id}", response_model=DeleteOutfitResponse)
def delete_outfit(
    outfit_id: int,
    db: DBSession,
    user_id: int = Query(..., description="User ID — must match the outfit owner"),
) -> DeleteOutfitResponse:
    """Delete a saved outfit.

    Returns 404 if the outfit does not exist or belongs to a different user.
    The ``outfit_items`` rows are removed automatically via the FK ON DELETE CASCADE.
    """
    outfit = db.get(Outfit, outfit_id)
    if outfit is None or outfit.user_id != user_id:
        raise HTTPException(status_code=404, detail="Outfit not found")
    db.delete(outfit)
    return DeleteOutfitResponse(status="deleted", outfit_id=outfit_id)


# ---------------------------------------------------------------------------
# POST /feedback
# ---------------------------------------------------------------------------


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(body: FeedbackRequest, db: DBSession, svc: SvcDep) -> FeedbackResponse:
    """Record user feedback on a suggested item.

    Publishes the rating to a Redis Stream (``fitgraph:feedback``) so that the
    retrain worker can consume it asynchronously.  If Redis is unreachable the
    handler falls back to a direct Postgres insert so the endpoint remains
    resilient — callers cannot distinguish the two paths from the response.

    Returns
    -------
    FeedbackResponse
        ``{"status": "queued"}`` when the event was published to Redis, or
        ``{"status": "ok"}`` when written directly to Postgres.
    """
    event = {
        "user_id": body.user_id,
        "query_item_id": body.query_item_id,
        "suggested_item_id": body.suggested_item_id,
        "rating": body.rating,
        "model_version": svc.current_version,
        "created_at": datetime.now(UTC).isoformat(),
    }

    try:
        from fitgraph.feedback.stream import get_redis, publish_rating  # noqa: PLC0415

        redis_client = get_redis()
        redis_client.ping()
        publish_rating(redis_client, event)
        return FeedbackResponse(status="queued")
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s); falling back to direct DB insert for feedback", exc
        )

    # Fallback: insert directly into the ratings table
    rating = Rating(
        user_id=body.user_id,
        query_item_id=body.query_item_id,
        suggested_item_id=body.suggested_item_id,
        rating=body.rating,
        model_version=svc.current_version,
        created_at=datetime.now(UTC),
    )
    db.add(rating)
    return FeedbackResponse(status="ok")


# ---------------------------------------------------------------------------
# GET /catalog/categories
# ---------------------------------------------------------------------------


@router.get("/catalog/categories", response_model=CategoryListResponse)
def catalog_categories(db: DBSession) -> CategoryListResponse:
    """Return all non-empty semantic categories with item counts, descending."""
    rows = list_categories(db)
    return CategoryListResponse(
        categories=[CategoryCount(category=r["category"], count=r["count"]) for r in rows]
    )


# ---------------------------------------------------------------------------
# GET /catalog/items
# ---------------------------------------------------------------------------


@router.get("/catalog/items", response_model=CatalogItemsResponse)
def catalog_items(
    db: DBSession,
    category: str = Query(..., description="Semantic category to browse"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogItemsResponse:
    """Return paginated items for a given semantic category."""
    items: list[Item] = list_items_by_category(db, category, limit=limit, offset=offset)
    return CatalogItemsResponse(
        category=category,
        limit=limit,
        offset=offset,
        items=[
            CatalogItemOut(
                item_id=it.id,
                title=it.title,
                semantic_category=it.semantic_category,
                image_path=it.image_path,
            )
            for it in items
        ],
    )


# ---------------------------------------------------------------------------
# GET /items/{item_id}/outfit-suggestions
# ---------------------------------------------------------------------------


@router.get("/items/{item_id}/outfit-suggestions", response_model=OutfitSuggestionsResponse)
def outfit_suggestions(
    item_id: str,
    svc: SvcDep,
    db: DBSession,
    per_category: int = Query(default=8, ge=1, le=50),
) -> OutfitSuggestionsResponse:
    """Return grouped per-category outfit suggestions for a catalog seed item."""
    _require_model(svc)

    try:
        result = svc.suggest_by_categories(item_id, db, per_category=per_category)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    seed_data = result["seed"]
    seed_out = CatalogItemOut(
        item_id=seed_data["item_id"],
        title=seed_data["title"],
        semantic_category=seed_data["semantic_category"],
        image_path=seed_data["image_path"],
    )

    suggestions_out: dict[str, list[OutfitSuggestionItem]] = {
        cat: [OutfitSuggestionItem(**item) for item in items]
        for cat, items in result["suggestions"].items()
    }

    return OutfitSuggestionsResponse(seed=seed_out, suggestions=suggestions_out)


# ---------------------------------------------------------------------------
# GET /catalog/search
# ---------------------------------------------------------------------------


@router.get("/catalog/search", response_model=CatalogSearchResponse)
def catalog_search(
    db: DBSession,
    q: str = Query(..., description="Full-text search query"),
    limit: int = Query(default=20, ge=1, le=100),
) -> CatalogSearchResponse:
    """Full-text catalog search via PostgreSQL tsvector."""
    items: list[Item] = search_items_by_tag(db, q, limit=limit)
    return CatalogSearchResponse(
        items=[
            CatalogItem(
                item_id=it.id,
                title=it.title,
                semantic_category=it.semantic_category,
                image_path=it.image_path,
                tags=it.tags,
            )
            for it in items
        ],
        total=len(items),
    )


# ---------------------------------------------------------------------------
# GET /images/{item_id}
# ---------------------------------------------------------------------------

_IMAGES_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "polyvore-outfit-dataset"
    / "polyvore_outfits"
    / "images"
)


@router.get("/images/{item_id}")
def serve_item_image(item_id: str) -> FileResponse:
    """Serve the JPEG image for a catalog item by its item_id."""
    # Sanitise: item_id must not contain path separators
    if "/" in item_id or "\\" in item_id or ".." in item_id:
        raise HTTPException(status_code=400, detail="Invalid item_id")
    image_path = _IMAGES_DIR / f"{item_id}.jpg"
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image not found: {item_id}")
    return FileResponse(str(image_path), media_type="image/jpeg")
