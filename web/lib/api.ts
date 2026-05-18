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
// /suggest
// ---------------------------------------------------------------------------

export interface SuggestionItem {
  item_id: string;
  score: number;
  title: string;
  semantic_category: string;
  image_path: string;
}

export interface SuggestResponse {
  query: { category: string | null };
  suggestions: SuggestionItem[];
}

export async function getSuggestions(
  image: File,
  text?: string,
  category?: string
): Promise<SuggestResponse> {
  const form = new FormData();
  form.append("image", image);
  if (text) form.append("text", text);
  if (category) form.append("category", category);
  return apiFetch<SuggestResponse>("/suggest", { method: "POST", body: form });
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

export async function createOutfit(
  userId: number,
  name: string,
  itemIds: string[]
): Promise<OutfitResponse> {
  return apiFetch<OutfitResponse>("/outfits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, name, item_ids: itemIds }),
  });
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

// ---------------------------------------------------------------------------
// /feedback
// ---------------------------------------------------------------------------

export interface FeedbackResponse {
  status: string;
}

export async function postFeedback(
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

// ---------------------------------------------------------------------------
// /catalog/search
// ---------------------------------------------------------------------------

export interface CatalogItem {
  item_id: string;
  title: string | null;
  semantic_category: string | null;
  image_path: string | null;
  tags: string[] | null;
}

export interface CatalogSearchResponse {
  items: CatalogItem[];
  total: number;
}

export async function searchCatalog(
  q: string,
  limit = 20
): Promise<CatalogSearchResponse> {
  return apiFetch<CatalogSearchResponse>(
    `/catalog/search?q=${encodeURIComponent(q)}&limit=${limit}`
  );
}
