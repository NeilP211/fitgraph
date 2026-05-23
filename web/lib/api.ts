/**
 * FitGraph API client — typed wrappers for every backend endpoint.
 * Base URL is configurable via NEXT_PUBLIC_API_URL (defaults to http://localhost:8000).
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Image URL helper
// ---------------------------------------------------------------------------

export function imageUrl(itemId: string): string {
  return `${BASE_URL}/images/${encodeURIComponent(itemId)}`;
}

// ---------------------------------------------------------------------------
// /healthz
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  model_version: string | null;
  p99_latency_ms: number | null;
}

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/healthz");
}

// ---------------------------------------------------------------------------
// /compatibility
// ---------------------------------------------------------------------------

export interface CompatibilityResponse {
  score: number;
}

export async function getCompatibility(
  itemIdA: string,
  itemIdB: string
): Promise<CompatibilityResponse> {
  return apiFetch<CompatibilityResponse>("/compatibility", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id_a: itemIdA, item_id_b: itemIdB }),
  });
}

// ---------------------------------------------------------------------------
// /catalog/categories
// ---------------------------------------------------------------------------

export interface CategoryCount {
  category: string;
  count: number;
}

export interface CategoryListResponse {
  categories: CategoryCount[];
}

export async function getCategories(): Promise<CategoryListResponse> {
  return apiFetch<CategoryListResponse>("/catalog/categories");
}

// ---------------------------------------------------------------------------
// /catalog/items
// ---------------------------------------------------------------------------

export interface CatalogItem {
  item_id: string;
  title: string | null;
  semantic_category: string | null;
  image_path: string | null;
  color?: string | null;
  brand?: string | null;
}

export interface CatalogItemsResponse {
  category: string;
  limit: number;
  offset: number;
  items: CatalogItem[];
}

export async function getCatalogItems(
  category: string,
  limit = 24,
  offset = 0,
  color?: string | null,
  brand?: string | null
): Promise<CatalogItemsResponse> {
  const params = new URLSearchParams({
    category,
    limit: String(limit),
    offset: String(offset),
  });
  if (color) params.set("color", color);
  if (brand) params.set("brand", brand);
  return apiFetch<CatalogItemsResponse>(`/catalog/items?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// /catalog/facets
// ---------------------------------------------------------------------------

export interface FacetValue {
  value: string;
  count: number;
}

export interface CatalogFacetsResponse {
  category: string;
  colors: FacetValue[];
  brands: FacetValue[];
}

export async function getCatalogFacets(
  category: string
): Promise<CatalogFacetsResponse> {
  return apiFetch<CatalogFacetsResponse>(
    `/catalog/facets?category=${encodeURIComponent(category)}`
  );
}

// ---------------------------------------------------------------------------
// /catalog/search
// ---------------------------------------------------------------------------

export interface CatalogSearchResponse {
  items: CatalogItem[];
  total: number;
}

/** Full-text catalog search (Postgres tsvector) via /catalog/search. */
export async function searchCatalog(
  q: string,
  limit = 24
): Promise<CatalogSearchResponse> {
  return apiFetch<CatalogSearchResponse>(
    `/catalog/search?q=${encodeURIComponent(q)}&limit=${limit}`
  );
}

// ---------------------------------------------------------------------------
// /items/{item_id}/outfit-suggestions
// ---------------------------------------------------------------------------

export interface SuggestionItem {
  item_id: string;
  score: number;
  title: string | null;
  semantic_category: string;
  image_path: string | null;
}

export interface OutfitSuggestionsResponse {
  seed: CatalogItem;
  suggestions: Record<string, SuggestionItem[]>;
}

export async function getOutfitSuggestions(
  itemId: string,
  perCategory = 8
): Promise<OutfitSuggestionsResponse> {
  return apiFetch<OutfitSuggestionsResponse>(
    `/items/${encodeURIComponent(itemId)}/outfit-suggestions?per_category=${perCategory}`
  );
}

// ---------------------------------------------------------------------------
// /outfits
// ---------------------------------------------------------------------------

export interface OutfitResponse {
  outfit_id: number;
  user_id: number | null;
  name: string | null;
  item_ids: string[];
}

export async function saveOutfit(params: {
  user_id: number;
  name: string;
  item_ids: string[];
}): Promise<OutfitResponse> {
  return apiFetch<OutfitResponse>("/outfits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

/** @deprecated Use saveOutfit instead */
export async function createOutfit(
  userId: number,
  name: string,
  itemIds: string[]
): Promise<OutfitResponse> {
  return saveOutfit({ user_id: userId, name, item_ids: itemIds });
}

export interface OutfitHistoryEntry {
  outfit_id: number;
  outfit_name: string | null;
  created_at: string | null;
  item_ids: string[];
}

export interface OutfitHistoryResponse {
  outfits: OutfitHistoryEntry[];
}

export async function getOutfits(userId: number): Promise<OutfitHistoryResponse> {
  return apiFetch<OutfitHistoryResponse>(`/outfits?user_id=${userId}`);
}

export interface DeleteOutfitResponse {
  status: string;
  outfit_id: number;
}

export async function deleteOutfit(
  outfitId: number,
  userId: number
): Promise<DeleteOutfitResponse> {
  return apiFetch<DeleteOutfitResponse>(
    `/outfits/${outfitId}?user_id=${userId}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// /feedback
// ---------------------------------------------------------------------------

export interface FeedbackResponse {
  status: string;
}

export async function sendFeedback(
  userId: number,
  queryItemId: string,
  suggestedItemId: string,
  rating: 1 | -1
): Promise<FeedbackResponse> {
  return apiFetch<FeedbackResponse>("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      query_item_id: queryItemId,
      suggested_item_id: suggestedItemId,
      rating,
    }),
  });
}

/** @deprecated Use sendFeedback instead */
export async function postFeedback(
  userId: number,
  queryItemId: string,
  suggestedItemId: string,
  rating: 1 | -1
): Promise<FeedbackResponse> {
  return sendFeedback(userId, queryItemId, suggestedItemId, rating);
}
