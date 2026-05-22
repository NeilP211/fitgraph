# FitGraph v2 — Catalog Outfit Builder — Design Spec

**Date:** 2026-05-22
**Status:** Approved for planning
**Builds on:** the completed FitGraph project (see `2026-05-17-fitgraph-design.md`).

## 1. Summary

Replace FitGraph's image-upload entry point with a **catalog browse + outfit
builder** flow. The user browses the existing Polyvore catalog by category,
picks a seed garment (e.g. a shirt), and the type-aware HGAT suggests compatible
items **grouped by complementary category** (bottoms, shoes, bags, jewellery,
…). The user assembles a full outfit by choosing one item per category and saves
it.

The ML core is unchanged — same type-aware HGAT (`v7`), same catalog, same
pgvector retrieval, same Redis feedback loop. Only the **query source** changes:
a catalog item picked by category instead of an uploaded image.

## 2. Motivation & spec alignment

The original spec's product line was "upload a piece you own, get suggestions."
This pivots the entry point to picking from a categorized catalog, which more
directly demonstrates "understanding outfit composition" and lets a recruiter
explore the product without supplying their own photos. The dataset, model, and
metrics (Compatibility AUC 0.848, FITB 0.623) are unaffected. The README/resume
wording changes from "upload a piece you own" to "browse a categorized catalog,
get compatible pairings."

## 3. Scope

### In scope
- Browse the catalog by category (paginated item grids).
- Outfit-builder view: seed item + per-complementary-category suggestion
  sections ranked by the type-aware model; select one per category; save.
- Reuse existing save-outfit, saved-outfits, and feedback features.
- New backend endpoints + queries; new/updated frontend pages.

### Out of scope / removed
- The image-upload `/suggest` flow and `UploadZone` UI are **removed** from the
  product. The underlying CLIP image-encoding code stays in the library (it is
  still used by the offline embeddings pipeline).
- No retraining, no new dataset — the seeded 71,967-item Polyvore catalog and
  the `v7` model are reused as-is.
- AWS deployment remains deferred.

## 4. Data

Reuse the seeded catalog: Postgres `items` (71,967 rows with
`semantic_category`, `title`, `image_path`) and `item_embeddings`
(pgvector `vector(256)`, the `v7` catalog embeddings). Images served at
`GET /images/{item_id}`. Categories present include `tops`, `bottoms`, `shoes`,
`bags`, `jewellery`, `outerwear`, `sunglasses`, `hats`, `accessories`,
`all-body` (dresses), `scarves`, etc.

## 5. Backend (FastAPI) — additions

All new endpoints reuse the existing `ModelService`, `db`, and `retrieval`
layers.

- `GET /catalog/categories` → `[{category, count}]`, ordered by count desc.
  New query `list_categories(session)`.
- `GET /catalog/items?category=&limit=&offset=` → paginated items in a category
  (`id, title, semantic_category, image_path`). New query
  `list_items_by_category(session, category, limit, offset)`.
- `GET /items/{item_id}/outfit-suggestions?per_category=` → the core endpoint.
  1. Load the seed item's embedding + `semantic_category` from the DB (404 if
     unknown / no embedding).
  2. Determine complementary categories = all catalog categories except the
     seed's own category.
  3. For each complementary category: category-filtered pgvector ANN
     (`SELECT e.item_id FROM item_embeddings e JOIN items i ON e.item_id=i.id
     WHERE i.semantic_category=:cat ORDER BY e.embedding <=> :vec LIMIT
     <candidate_pool>`), then **re-rank** those candidates by the type-aware
     score between the seed and each candidate (using the
     `(seed_category, candidate_category)` subspace), keep top `per_category`.
  4. Return `{seed: {...}, suggestions: {category: [{item_id, score, title,
     semantic_category, image_path}]}}`. Skip categories with no candidates.
  New `ModelService.suggest_by_categories(seed_item_id, session, per_category)`.
- `POST /outfits`, `GET /outfits`, `POST /feedback`, `GET /catalog/search`,
  `GET /healthz`, `GET /images/{item_id}` — **unchanged**, reused.
- Remove the `POST /suggest` (multipart upload) route and its tests; keep
  `ClipEncoder` / `TextEncoder` / `fuse` in the library.

## 6. Frontend (Next.js + TS + Tailwind)

- **Browse (home `/`)** — replaces the upload home. Category chips/pills (from
  `/catalog/categories`); selecting one shows a responsive item grid from
  `/catalog/items` with "load more" pagination. Each card: image, title (or
  category fallback), category tag. Clicking a card seeds the outfit builder.
- **Outfit builder (`/build/[itemId]`)** — pinned seed item at top; below it one
  section per complementary category (from `/items/{id}/outfit-suggestions`),
  each a horizontal row/grid of suggestion cards with a match-score badge and
  thumbs up/down (→ `/feedback`, with `query_item_id` = seed). Selecting a card
  toggles it into a sticky **"Your outfit" tray**; the tray has a name field and
  **Save** (→ `POST /outfits` with the seed + selected item ids).
- **Saved outfits (`/outfits`)** — unchanged; lists saved outfits with images.
- Remove `UploadZone` and the upload flow; update Nav (Browse / Saved outfits).
- Cards are image-first so empty Polyvore titles still look clean.

## 7. Testing

- pytest: `list_categories` and `list_items_by_category` query tests (isolated
  with unique-token / category fixtures, robust to the seeded catalog); endpoint
  tests for `/catalog/categories`, `/catalog/items`, and
  `/items/{id}/outfit-suggestions` (synthetic seed item + a few categorized
  items + embeddings; assert grouping, per-category cap, and that the seed's own
  category is excluded). Remove the `/suggest` upload tests.
- Frontend: `npm run lint` + `npm run build`; a browser smoke test of
  browse → pick → build → save against the live API.
- Full suite green; ruff clean.

## 8. Success criteria

- A user can browse a category, pick an item, see compatible suggestions grouped
  by complementary category, assemble an outfit, and save it — end to end
  against the live stack.
- The type-aware model drives the per-category rankings (cross-category subspace
  scoring).
- Tests pass; README/resume wording updated to the browse-based flow.
