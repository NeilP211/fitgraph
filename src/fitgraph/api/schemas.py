"""Pydantic request / response schemas for the FitGraph API."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    model_version: str | None
    p99_latency_ms: float | None = None


# ---------------------------------------------------------------------------
# /compatibility
# ---------------------------------------------------------------------------


class CompatibilityRequest(BaseModel):
    item_id_a: str = Field(..., description="ID of the first catalog item")
    item_id_b: str = Field(..., description="ID of the second catalog item")


class CompatibilityResponse(BaseModel):
    score: float = Field(..., description="Type-aware compatibility score in [-1, 1]")


# ---------------------------------------------------------------------------
# /suggest (kept for legacy serving.suggest; SuggestResponse removed)
# ---------------------------------------------------------------------------


class SuggestionItem(BaseModel):
    item_id: str
    score: float
    title: str
    semantic_category: str
    image_path: str


# ---------------------------------------------------------------------------
# /catalog/categories
# ---------------------------------------------------------------------------


class CategoryCount(BaseModel):
    category: str
    count: int


class CategoryListResponse(BaseModel):
    categories: list[CategoryCount]


# ---------------------------------------------------------------------------
# /catalog/items
# ---------------------------------------------------------------------------


class CatalogItemOut(BaseModel):
    item_id: str
    title: str | None
    semantic_category: str | None
    image_path: str | None
    color: str | None = None
    brand: str | None = None


class CatalogItemsResponse(BaseModel):
    category: str
    limit: int
    offset: int
    items: list[CatalogItemOut]


class FacetValue(BaseModel):
    value: str
    count: int


class CatalogFacetsResponse(BaseModel):
    category: str
    colors: list[FacetValue]
    brands: list[FacetValue]


# ---------------------------------------------------------------------------
# /items/{item_id}/outfit-suggestions
# ---------------------------------------------------------------------------


class OutfitSuggestionItem(BaseModel):
    item_id: str
    score: float
    title: str
    semantic_category: str
    image_path: str


class OutfitSuggestionsResponse(BaseModel):
    seed: CatalogItemOut
    suggestions: dict[str, list[OutfitSuggestionItem]]


# ---------------------------------------------------------------------------
# /outfits
# ---------------------------------------------------------------------------


class CreateOutfitRequest(BaseModel):
    user_id: int
    name: str | None = None
    item_ids: list[str] = Field(default_factory=list)


class OutfitItemOut(BaseModel):
    item_id: str
    position: int | None

    model_config = {"from_attributes": True}


class OutfitResponse(BaseModel):
    outfit_id: int
    user_id: int | None
    name: str | None
    item_ids: list[str]

    model_config = {"from_attributes": True}


class OutfitHistoryEntry(BaseModel):
    outfit_id: int
    outfit_name: str | None
    created_at: str | None
    item_ids: list[str]


class OutfitHistoryResponse(BaseModel):
    outfits: list[OutfitHistoryEntry]


class DeleteOutfitResponse(BaseModel):
    status: str
    outfit_id: int


# ---------------------------------------------------------------------------
# /feedback
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    user_id: int
    query_item_id: str
    suggested_item_id: str
    rating: int = Field(..., description="Numeric rating, e.g. 1 (good) / -1 (bad)")


class FeedbackResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# /catalog/search
# ---------------------------------------------------------------------------


class CatalogItem(BaseModel):
    item_id: str
    title: str | None
    semantic_category: str | None
    image_path: str | None
    tags: list[str] | None


class CatalogSearchResponse(BaseModel):
    items: list[CatalogItem]
    total: int
