# FitGraph — Outfit Compatibility GNN — Design Spec

**Date:** 2026-05-17
**Status:** Approved for planning

## 1. Summary

FitGraph is a graph neural network that learns garment compatibility from
co-occurrence in real outfits. A user uploads a garment they own; FitGraph
suggests catalog items to pair with it. It includes a real product UI and a
feedback loop that drives periodic active retraining.

The ML story: most fashion recommenders return *similar* items. FitGraph
returns *compatible* items — it understands outfit composition by learning from
how garments are actually worn together.

## 2. Scope

### In scope
- Data pipeline: download Polyvore Outfits, generate embeddings, build graph.
- Heterogeneous Graph Attention Network (HGAT) over a garment↔outfit bipartite
  graph.
- Contrastive training: InfoNCE loss with hard-negative mining.
- Evaluation suite: compatibility AUC, fill-in-the-blank (FITB) accuracy,
  recall@K, qualitative outfit grids.
- FastAPI inference service: compatibility queries and suggestion retrieval.
- pgvector retrieval over learned item embeddings.
- Postgres catalog, user accounts, outfit history — with non-trivial queries
  (joins, full-text search on tags).
- Redis Streams feedback ingestion loop: ratings flow in, batch-processed.
- Active-learning retrain trigger: retraining fires when feedback volume crosses
  a threshold; models are versioned.
- Next.js + TypeScript + Tailwind frontend: image upload, suggestions grid,
  save-outfit, rate-suggestion.
- GitHub Actions CI: runs tests and lint.

### Out of scope (deferred, documented but not wired)
- AWS deployment (ECS Fargate, S3, CloudWatch, IAM), AWS CDK.
- Modal GPU training infrastructure.
- W&B is **optional** — opt-in via environment variable; default logging is
  console + local CSV/TensorBoard so the repo runs with zero external accounts.
- Live public demo deployment.

The README will contain a clearly-labeled "Production deployment (not wired)"
section describing the intended AWS architecture, so the full design intent is
visible without claiming it is live.

### Explicitly dropped
- Supplemental data scraped from public fashion sites — fragile and legally
  ambiguous. Polyvore alone (21k outfits / 365k items) is sufficient.

## 3. Dataset

**Polyvore Outfits**, downloaded via the **Kaggle API** (token already
configured on the development machine).

- The pipeline supports the **full** dataset (~21k outfits, ~365k items).
- The **default config trains on a configurable subset (~5k outfits)** so a
  clean end-to-end run completes in reasonable time on Apple Silicon (MPS).
- A `--full` flag scales the pipeline to the complete dataset.
- The README reports metrics for whatever run was actually executed — no
  inflated numbers.

Train/val/test splits are **outfit-disjoint**: an outfit appears in exactly one
split, preventing co-occurrence leakage across splits.

## 4. Architecture

```
projects/fitgraph/
  src/fitgraph/
    config.py      Central config (paths, hyperparameters, env-driven).
    data/          Polyvore download, parsing, outfit-disjoint splits.
    embeddings/    CLIP (open_clip ViT-B/32) image encoder;
                   sentence-transformers text encoder; feature fusion.
    graph/         Bipartite heterogeneous graph builder (PyG HeteroData),
                   node types: `garment`, `outfit`.
    models/        HGAT model definition.
    training/      InfoNCE loss, hard-negative mining, train loop,
                   model versioning/checkpointing.
    eval/          AUC, FITB accuracy, recall@K, qualitative outfit grids.
    retrieval/     pgvector similarity search client.
    db/            Postgres schema + query layer (joins, FTS on tags).
    feedback/      Redis Streams producer/consumer, active-learning trigger.
    api/           FastAPI app: routes, schemas, model serving.
  scripts/         download_data, build_embeddings, build_graph, train,
                   evaluate, retrain (CLI entry points).
  tests/           pytest suite.
  web/             Next.js + TypeScript + Tailwind frontend.
  data/            (gitignored) datasets, embeddings, checkpoints.
  docker-compose.yml   Postgres (+pgvector extension), Redis.
  .github/workflows/ci.yml
  docs/            architecture.md + this spec.
  README.md
```

The Python package `fitgraph` is single and shared: the API imports model and
retrieval code directly rather than duplicating it.

## 5. Data flow

**Offline (training):**
1. Download Polyvore via Kaggle API.
2. Generate CLIP image embeddings + sentence-transformer text embeddings per
   item; fuse into a single item feature vector.
3. Build the garment↔outfit bipartite `HeteroData` graph.
4. Train the HGAT with InfoNCE contrastive loss + hard-negative mining.
5. Export learned item embeddings into pgvector; save a versioned checkpoint.

**Online (inference):**
1. User uploads a garment image.
2. Image is CLIP-embedded; HGAT projects it into the compatibility space.
3. pgvector ANN search over catalog item embeddings.
4. Ranked compatibility suggestions returned.

**Feedback (active learning):**
1. User rates a suggestion in the UI.
2. Rating event is published to a Redis Stream.
3. A batch consumer drains the stream and persists ratings to Postgres.
4. When cumulative new-rating volume crosses a threshold, the retrain script
   runs and produces a **new versioned model**; the API can hot-swap to it.

## 6. Model and training

- **Graph:** `HeteroData` with `garment` and `outfit` node types; edges connect
  a garment to every outfit it appears in (bipartite).
- **Node features:** item nodes carry fused CLIP-image + text embeddings,
  projected to the model hidden dimension.
- **HGAT:** heterogeneous graph attention layers propagate signal across the
  bipartite structure to produce compatibility-aware item embeddings.
- **Loss:** InfoNCE contrastive loss. Positives = items co-occurring in the same
  outfit. **Hard negatives** = items visually similar (small CLIP distance) to
  the anchor that are *not* co-worn — these force the model to learn
  compatibility beyond visual similarity.
- **Splits:** outfit-disjoint train/val/test.

## 7. Evaluation

- **Compatibility AUC** on the test split — target > 0.85.
- **Fill-in-the-blank accuracy** — target > 60%.
- **Recall@K** for the retrieval task.
- **Qualitative outfit grids** — rendered image grids of suggested pairings,
  saved as artifacts for the README.
- **Inference latency** — P99 measured locally, target < 100ms.

All targets are *chased*; the README reports the actual measured values.

## 8. API surface (FastAPI)

- `POST /compatibility` — score compatibility between two items.
- `POST /suggest` — upload/identify a garment, return ranked suggestions.
- `POST /outfits` — save an outfit (authenticated).
- `GET  /outfits` — list a user's saved outfits (joins outfit history).
- `POST /feedback` — submit a rating for a suggestion (publishes to Redis).
- `GET  /catalog/search` — full-text search over item tags.
- `GET  /healthz` — health/readiness.

## 9. Database (Postgres)

- Tables: `users`, `items` (catalog), `item_embeddings` (pgvector column),
  `outfits`, `outfit_items` (join), `ratings`, `model_versions`.
- Non-trivial queries: outfit-history joins, full-text search on item tags,
  aggregate rating volume for the retrain trigger.

## 10. Frontend (Next.js + TS + Tailwind)

- Image upload of a garment the user owns.
- Suggestions grid showing compatible catalog items with scores.
- "Save outfit" to persist a chosen combination.
- Rate a suggestion (thumbs up/down) — feeds the feedback loop.
- Deployed locally; Vercel deployment deferred.

## 11. Infrastructure (local)

- `docker-compose.yml`: Postgres (with the pgvector extension) and Redis.
- Everything runs on the development machine; no cloud accounts required.
- Apple Silicon MPS used for embedding generation and training where available.

## 12. CI/CD

- GitHub Actions workflow: install deps, run pytest, run lint (ruff + the web
  app's lint). No deployment step.

## 13. Success criteria

- The repo runs end-to-end locally from a documented sequence of commands.
- A real subset training run is executed during the build; the resulting
  checkpoint is shipped and its actual AUC/FITB numbers are in the README.
- All phases build cleanly and the full test suite passes; status is reported
  at each phase boundary.
- README and `docs/architecture.md` clearly explain the system, the ML story,
  and the deferred production architecture.

## 14. Build phases

1. **Scaffold** — repo structure, packaging, config, docker-compose, README skeleton.
2. **Data pipeline** — Kaggle download, parsing, outfit-disjoint splits.
3. **Embeddings** — CLIP image + text encoders, feature fusion.
4. **Graph** — bipartite `HeteroData` builder.
5. **Model + training** — HGAT, InfoNCE loss, hard-negative mining, train loop,
   versioning. Execute a real subset training run.
6. **Evaluation** — AUC, FITB, recall@K, qualitative grids; record real numbers.
7. **Database + retrieval** — Postgres schema, query layer, pgvector retrieval.
8. **Inference API** — FastAPI routes, model serving, latency measurement.
9. **Feedback loop** — Redis Streams ingestion, active-learning retrain trigger.
10. **Frontend** — Next.js upload / suggestions / save / rate.
11. **CI + docs** — GitHub Actions, README finalization, architecture doc.

Each phase ends with a build + full test-suite run and a verified status report.
