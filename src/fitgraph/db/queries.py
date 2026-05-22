"""Non-trivial database query helpers for FitGraph."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from fitgraph.db.models import Item, ModelVersion, Outfit, OutfitItem, Rating


def user_outfit_history(session: Session, user_id: int) -> list[dict]:
    """Return all outfits for *user_id* with their ordered items.

    Each element of the returned list is a dict::

        {
            "outfit_id": int,
            "outfit_name": str | None,
            "created_at": datetime | None,
            "items": [Item, ...],   # ordered by OutfitItem.position
        }
    """
    outfits = (
        session.query(Outfit)
        .options(
            selectinload(Outfit.outfit_items).selectinload(OutfitItem.item)
        )
        .filter(Outfit.user_id == user_id)
        .order_by(Outfit.created_at)
        .all()
    )

    results: list[dict] = []
    for outfit in outfits:
        sorted_oi = sorted(
            outfit.outfit_items,
            key=lambda oi: (oi.position is None, oi.position),
        )
        results.append(
            {
                "outfit_id": outfit.id,
                "outfit_name": outfit.name,
                "created_at": outfit.created_at,
                "items": [oi.item for oi in sorted_oi],
            }
        )
    return results


def search_items_by_tag(session: Session, query: str, limit: int = 20) -> list[Item]:
    """Full-text search over ``items.search_doc`` using *query*.

    Uses ``plainto_tsquery('english', :q)`` and orders results by
    ``ts_rank`` descending.
    """
    tsquery = func.plainto_tsquery("english", query)
    ts_rank = func.ts_rank(Item.search_doc, tsquery)

    return (
        session.query(Item)
        .filter(Item.search_doc.op("@@")(tsquery))
        .order_by(ts_rank.desc())
        .limit(limit)
        .all()
    )


def list_categories(session: Session) -> list[dict]:
    """Return [{"category", "count"}] for non-null categories, count desc."""
    rows = (
        session.query(Item.semantic_category, func.count(Item.id))
        .filter(Item.semantic_category.isnot(None), Item.semantic_category != "")
        .group_by(Item.semantic_category)
        .order_by(func.count(Item.id).desc())
        .all()
    )
    return [{"category": c, "count": int(n)} for c, n in rows]


def list_items_by_category(
    session: Session, category: str, limit: int = 24, offset: int = 0
) -> list[Item]:
    """Items in a category, stable-ordered by id, paginated."""
    return (
        session.query(Item)
        .filter(Item.semantic_category == category)
        .order_by(Item.id)
        .limit(limit)
        .offset(offset)
        .all()
    )


def rating_volume_since(session: Session, model_version: str) -> int:
    """Count ratings collected since *model_version* was created.

    Returns the number of :class:`~fitgraph.db.models.Rating` rows whose
    ``created_at`` is strictly after the ``created_at`` of the named
    :class:`~fitgraph.db.models.ModelVersion`.  Returns 0 if the version is
    not found.
    """
    mv = session.get(ModelVersion, model_version)
    if mv is None or mv.created_at is None:
        return 0

    count = (
        session.query(func.count(Rating.id))
        .filter(Rating.created_at > mv.created_at)
        .scalar()
    )
    return count or 0
