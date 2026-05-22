# Catalog Outfit Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace FitGraph's image-upload entry point with a catalog browse + per-category outfit-builder flow, driven by the existing type-aware HGAT (`v7`).

**Architecture:** Add three read endpoints (categories, items-by-category, grouped outfit suggestions) on top of the existing `db`/`retrieval`/`ModelService` layers; rebuild the Next.js home as a category browser + an outfit-builder page; remove the upload UI/route. No retraining — reuse the seeded 71,967-item catalog and `v7` embeddings.

**Tech Stack:** FastAPI + SQLAlchemy 2 + pgvector, PyTorch (type-aware scorer), Next.js 15 + TS + Tailwind, pytest.

---

## Conventions
- Python: `.venv/bin/ruff check src tests scripts` + `.venv/bin/python -m pytest -q` from repo root.
- DB/Redis tests skip gracefully if services are down; isolate writes (savepoint rollback / unique tokens) so they're robust to the seeded catalog.
- Commit after each task; push at the end (`git push origin main`). **Never rewrite history.**
- Frontend: `cd web && npm run lint && npm run build`.

## File structure
```
src/fitgraph/db/queries.py            + list_categories, list_items_by_category
src/fitgraph/retrieval/pgvector_store.py  + query_by_category
src/fitgraph/api/serving.py           + ModelService.suggest_by_categories
src/fitgraph/api/schemas.py           + Category/CatalogItems/OutfitSuggestions models; - SuggestResponse
src/fitgraph/api/routes.py            + 3 routes; - POST /suggest
web/lib/api.ts                        + getCategories/getCatalogItems/getOutfitSuggestions; - suggest
web/components/CategoryNav.tsx        (new)
web/components/BrowseGrid.tsx         (new)
web/components/OutfitBuilder.tsx      (new)
web/components/OutfitTray.tsx         (new)
web/app/page.tsx                      (rewrite: Browse)
web/app/build/[itemId]/page.tsx       (new)
web/components/UploadZone.tsx         (delete)
tests/db/test_queries.py              + category query tests
tests/api/test_routes.py              + new endpoint tests; - TestSuggest
tests/api/test_serving.py             + suggest_by_categories test
```

---

## Task 1: `list_categories` query

**Files:** Modify `src/fitgraph/db/queries.py`; Test `tests/db/test_queries.py`.

- [ ] **Write failing test** in `tests/db/test_queries.py` (new class `TestListCategories`):
```python
def test_returns_categories_with_counts(self, session):
    _seed_item(session, "cat_a1", title="x", cat="zqxcat_tops")
    _seed_item(session, "cat_a2", title="y", cat="zqxcat_tops")
    _seed_item(session, "cat_b1", title="z", cat="zqxcat_shoes")
    session.flush()
    rows = list_categories(session)
    by_cat = {r["category"]: r["count"] for r in rows}
    assert by_cat["zqxcat_tops"] == 2
    assert by_cat["zqxcat_shoes"] == 1
```
Add `list_categories` to the existing import from `fitgraph.db.queries`.
- [ ] **Run** `.venv/bin/python -m pytest tests/db/test_queries.py::TestListCategories -q` → FAIL (ImportError).
- [ ] **Implement** in `queries.py`:
```python
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
```
Add `from sqlalchemy import func` if not present.
- [ ] **Run** the test → PASS.
- [ ] **Commit:** `git add -A && git commit -m "feat(db): list_categories query"`

## Task 2: `list_items_by_category` query

**Files:** Modify `src/fitgraph/db/queries.py`; Test `tests/db/test_queries.py`.

- [ ] **Write failing test** (`TestListItemsByCategory`):
```python
def test_paginates_within_category(self, session):
    for i in range(5):
        _seed_item(session, f"lic_{i}", title=f"item{i}", cat="zqxcat_bottoms")
    _seed_item(session, "lic_other", title="other", cat="zqxcat_hats")
    session.flush()
    page = list_items_by_category(session, "zqxcat_bottoms", limit=2, offset=0)
    assert len(page) == 2
    assert all(it.semantic_category == "zqxcat_bottoms" for it in page)
    page2 = list_items_by_category(session, "zqxcat_bottoms", limit=2, offset=2)
    assert len(page2) == 2
    assert {it.id for it in page} & {it.id for it in page2} == set()
```
- [ ] **Run** → FAIL.
- [ ] **Implement:**
```python
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
```
- [ ] **Run** → PASS.
- [ ] **Commit:** `git add -A && git commit -m "feat(db): list_items_by_category query"`

## Task 3: category-filtered pgvector ANN

**Files:** Modify `src/fitgraph/retrieval/pgvector_store.py`; Test `tests/retrieval/test_pgvector_store.py`.

- [ ] **Write failing test** (`test_query_by_category_filters`): seed 2 items in category "qa" and 1 in "qb" (insert into `items` + `item_embeddings` via the test's existing helpers), then:
```python
res = query_by_category(session, vec, "qa", k=10)
ids = [r[0] for r in res]
assert all(i in {"qa1", "qa2"} for i in ids)
assert "qb1" not in ids
```
- [ ] **Run** → FAIL.
- [ ] **Implement** in `pgvector_store.py` (mirror the existing `query`):
```python
def query_by_category(
    session: Session, vector: list[float], category: str, k: int = 40
) -> list[tuple[str, float]]:
    """Category-filtered cosine-distance ANN over item_embeddings."""
    stmt = text(
        """
        SELECT e.item_id,
               e.embedding <=> CAST(:vec AS vector(256)) AS cosine_dist
        FROM   item_embeddings e
        JOIN   items i ON i.id = e.item_id
        WHERE  i.semantic_category = :cat
        ORDER BY cosine_dist
        LIMIT  :k
        """
    )
    rows = session.execute(
        stmt, {"vec": str(vector), "cat": category, "k": k}
    ).fetchall()
    return [(row.item_id, float(row.cosine_dist)) for row in rows]
```
- [ ] **Run** → PASS.
- [ ] **Commit:** `git add -A && git commit -m "feat(retrieval): category-filtered pgvector ANN"`

## Task 4: `ModelService.suggest_by_categories`

**Files:** Modify `src/fitgraph/api/serving.py`; Test `tests/api/test_serving.py`.

- [ ] **Write failing test** in `test_serving.py`: using the existing synthetic-checkpoint + synthetic-DB fixtures, seed a "tops" seed item plus a few "bottoms" and "shoes" items (with embeddings), then:
```python
out = svc.suggest_by_categories("seed_top", session, per_category=2)
assert out["seed"]["item_id"] == "seed_top"
assert "tops" not in out["suggestions"]            # own category excluded
assert all(len(v) <= 2 for v in out["suggestions"].values())
for cat, items in out["suggestions"].items():
    assert all(it["semantic_category"] == cat for it in items)
```
- [ ] **Run** → FAIL.
- [ ] **Implement** `suggest_by_categories(self, seed_item_id, session, per_category=8)`:
  - Guard `is_loaded`; import `Item`, `ItemEmbedding`, and `query_by_category`.
  - Load seed `Item` + its `ItemEmbedding` (raise `KeyError`/return None signalling for the route to 404 if missing).
  - `categories = [c["category"] for c in list_categories(session) if c["category"] != seed.semantic_category]`.
  - For each category: `cand = query_by_category(session, seed_emb.tolist(), cat, k=5*per_category)`; fetch those items+embeddings; re-rank with `self.score(seed_emb, seed.semantic_category, cand_emb, cat)`; keep top `per_category`; build dicts `{item_id, score, title, semantic_category, image_path}`.
  - Skip categories with no candidates.
  - Return `{"seed": {item_id,title,semantic_category,image_path}, "suggestions": {cat: [...]}}`.
- [ ] **Run** → PASS.
- [ ] **Commit:** `git add -A && git commit -m "feat(serving): suggest_by_categories grouped outfit suggestions"`

## Task 5: schemas + routes (add 3, remove /suggest)

**Files:** Modify `src/fitgraph/api/schemas.py`, `src/fitgraph/api/routes.py`; Test `tests/api/test_routes.py`.

- [ ] **schemas.py:** add `CategoryCount{category:str,count:int}`, `CategoryListResponse{categories:list[CategoryCount]}`, `CatalogItem{item_id,title,semantic_category,image_path}` (reuse existing item schema if present), `CatalogItemsResponse{category:str,limit:int,offset:int,items:list[CatalogItem]}`, `OutfitSuggestionItem{item_id,score,title,semantic_category,image_path}`, `OutfitSuggestionsResponse{seed:CatalogItem,suggestions:dict[str,list[OutfitSuggestionItem]]}`. Remove `SuggestResponse` (and the `SuggestQuery`/related model if present).
- [ ] **routes.py:** remove the `@router.post("/suggest")` handler. Add:
  - `@router.get("/catalog/categories")` → `list_categories(db)`.
  - `@router.get("/catalog/items")` (params `category: str`, `limit: int = 24`, `offset: int = 0`) → `list_items_by_category`.
  - `@router.get("/items/{item_id}/outfit-suggestions")` (param `per_category: int = 8`) → `_require_model(svc).suggest_by_categories(...)`; return 404 if the seed item is unknown/embedding missing.
- [ ] **test_routes.py:** remove `TestSuggest`. Add `TestCatalogCategories`, `TestCatalogItems`, `TestOutfitSuggestions` (seed synthetic categorized items+embeddings + synthetic model; assert: categories include seeded cats with counts; items endpoint paginates and filters; outfit-suggestions returns `seed`, excludes the seed's own category, caps per category, 404 for a bogus seed id).
- [ ] **Run** `.venv/bin/ruff check src tests && .venv/bin/python -m pytest -q tests/api tests/db tests/retrieval` → all PASS.
- [ ] **Commit:** `git add -A && git commit -m "feat(api): catalog browse + grouped outfit-suggestion endpoints; remove upload route"`

## Task 6: frontend API client

**Files:** Modify `web/lib/api.ts`.

- [ ] Add typed functions + types: `getCategories(): Promise<{categories:{category:string;count:number}[]}>`, `getCatalogItems(category, limit, offset)`, `getOutfitSuggestions(itemId, perCategory)`. Keep `saveOutfit`, `getOutfits`, `sendFeedback`, `imageUrl`. Remove the `suggest` (upload) function and its types.
- [ ] **Verify** `cd web && npm run lint`.
- [ ] **Commit:** `git add -A && git commit -m "feat(web): api client for browse + outfit suggestions"`

## Task 7: Browse home + category nav

**Files:** Create `web/components/CategoryNav.tsx`, `web/components/BrowseGrid.tsx`; rewrite `web/app/page.tsx`; update `web/components/Nav.tsx`; delete `web/components/UploadZone.tsx`.

- [ ] `CategoryNav`: fetches `/catalog/categories`, renders selectable category pills (with counts).
- [ ] `BrowseGrid`: given a category, fetches `/catalog/items` (paginated), renders a responsive image-first card grid (title falls back to the category label); a "Load more" button increments `offset`. Each card links to `/build/<item_id>`.
- [ ] `page.tsx`: compose `CategoryNav` + `BrowseGrid` with a selected-category state (default = first/most-populous category). Loading/empty/error states.
- [ ] `Nav.tsx`: links → Browse (`/`) and Saved outfits (`/outfits`). Remove any upload link.
- [ ] Delete `UploadZone.tsx`.
- [ ] **Verify** `cd web && npm run lint && npm run build`.
- [ ] **Commit:** `git add -A && git commit -m "feat(web): catalog browse home with category nav"`

## Task 8: Outfit builder page

**Files:** Create `web/app/build/[itemId]/page.tsx`, `web/components/OutfitBuilder.tsx`, `web/components/OutfitTray.tsx`; reuse `SuggestionCard.tsx` (adapt props if needed) and `SaveOutfitModal.tsx`.

- [ ] `build/[itemId]/page.tsx`: reads `itemId` from route params, renders `OutfitBuilder`.
- [ ] `OutfitBuilder`: fetches `/items/{itemId}/outfit-suggestions`; pins the seed item; renders one section per category in `suggestions`, each a row of `SuggestionCard`s (image, match-score badge, thumbs up/down → `sendFeedback` with `query_item_id=itemId`). Clicking a card toggles it into the tray (one selection per category).
- [ ] `OutfitTray`: sticky panel showing the seed + selected items, a name input, and Save → `saveOutfit({user_id:1, name, item_ids:[seed, ...selected]})`; success confirmation linking to `/outfits`. Reuse `SaveOutfitModal` if it fits.
- [ ] Loading/empty/error states throughout.
- [ ] **Verify** `cd web && npm run lint && npm run build`.
- [ ] **Commit:** `git add -A && git commit -m "feat(web): per-category outfit builder"`

## Task 9: integration smoke test + docs

**Files:** Modify `README.md`, `docs/architecture.md` (entry-point wording); verify live stack.

- [ ] Ensure services up (Postgres:5432 with catalog, Redis, model `v7`). Start API on a free port and frontend pointed at it.
- [ ] Browser smoke test (agent-browser or Playwright): load Browse → select a category → grid shows items with images → click an item → builder shows per-category suggestion sections with scores → select items → save outfit → confirm it appears on `/outfits`. Capture `docs/assets/screenshot.png` (replace the upload screenshot). Fix any integration bug found.
- [ ] Update `README.md` and `docs/architecture.md`: change the entry-point description and resume bullet from "upload a piece you own" to "browse a categorized catalog, pick a seed garment, get compatible items grouped by category." Keep all ML numbers.
- [ ] **Verify** `.venv/bin/ruff check src tests scripts && .venv/bin/python -m pytest -q` (full suite green) and `cd web && npm run build`.
- [ ] **Commit + push:** `git add -A && git commit -m "feat: catalog outfit-builder end-to-end + docs" && git push origin main`

---

## Self-Review
- **Spec coverage:** browse categories (T1,T7), browse items (T2,T7), category-filtered retrieval (T3), grouped type-aware suggestions (T4,T5,T8), endpoints (T5), remove upload (T5,T7), frontend builder + save + feedback reuse (T6–T8), tests (T1–T5,T9), docs/wording (T9). All spec sections mapped.
- **Placeholders:** none — concrete signatures, code, and commands throughout.
- **Type consistency:** `list_categories`→`[{category,count}]` used identically in T1/T5/T4; `list_items_by_category(session,category,limit,offset)` consistent T2/T5; `query_by_category(session,vector,category,k)` consistent T3/T4; `suggest_by_categories(seed_item_id,session,per_category)` returns `{seed, suggestions:{cat:[...]}}` consistent T4/T5/T8.
