# FitGraph — Architecture

## Overview and the ML story

Most fashion recommenders return *similar* items — if you have a blue blazer they
suggest other blue blazers. FitGraph does something different: it returns
*compatible* items, things that actually go well together in an outfit. That
distinction matters because compatibility is not the same as similarity; a top
should pair with bottoms, not other tops.

FitGraph learns compatibility by observing how garments are co-worn in real
outfits. The training set comes from **Polyvore Outfits** (21k curated outfits,
~365k items), a widely-used benchmark dataset for fashion compatibility research
downloaded via the Kaggle API. By training a graph neural network over the
garment co-occurrence structure, the model learns to tell apart "worn together"
from "visually similar but never combined".

---

## System components and data flow

### Offline pipeline (training)

```
Polyvore Outfits (Kaggle)
        │
        ▼
  data/polyvore.py        Parse JSON into Item / Outfit dataclasses
  data/splits.py          Outfit-disjoint train / val / test split
        │
        ▼
  embeddings/
    clip_encoder.py       open_clip ViT-B/32 → 512-dim image vector
    text_encoder.py       sentence-transformers MiniLM-L6-v2 → 384-dim text vector
    fusion.py             Concat + L2-normalise → 896-dim fused vector
        │
        ▼
  graph/builder.py        Build PyG HeteroData bipartite graph
                          garment nodes (x = fused 896-dim embeddings)
                          outfit nodes  (x = zeros, learned via message passing)
                          edges: ('garment','in','outfit') and reverse
        │
        ▼
  training/trainer.py     Mini-batch subgraph training (TRAIN outfits only)
  training/loss.py        Type-aware InfoNCE contrastive loss
  training/negatives.py   CLIP-mined hard-negative pool per step
        │
        ▼
  data/models/vN/         Versioned checkpoint: model.pt + meta.json + type_index.json
        │
        ▼
  scripts/seed_catalog.py Export learned garment embeddings → pgvector
```

The train/val/test split is **outfit-disjoint**: every outfit appears in exactly
one partition, so no garment co-occurrence signal leaks between splits.

### Serving path (online inference)

```
User browses the categorized catalog (Next.js frontend)
        │
        ▼
  GET /catalog/categories  (FastAPI)  ← list all semantic categories with item counts
  GET /catalog/items       (FastAPI)  ← paginated items by category
        │
        ▼
  User picks a seed garment → navigates to the outfit builder
        │
        ▼
  GET /items/{id}/outfit-suggestions  (FastAPI)
        │
        ▼
  api/serving.py          Load seed item embedding from pgvector
  retrieval/pgvector_store.py   Category-filtered ANN cosine search per category
        │
        ▼
  models/type_aware.py    TypeAwareScorer re-ranks per-category candidates
        │
        ▼
  Grouped per-category suggestions returned to the outfit builder
```

### Feedback path (active learning)

```
User rates a suggestion (thumbs up/down) in the frontend
        │
        ▼
  POST /feedback  (FastAPI)
        │
        ▼
  feedback/stream.py      XADD event to Redis Stream 'fitgraph:feedback'
        │
        ▼
  feedback/stream.py      Batch consumer (XREADGROUP) drains stream,
                          persists Rating rows to Postgres, XACKs messages
        │
        ▼
  feedback/trigger.py     should_retrain() checks cumulative new-rating
                          volume against settings.retrain_threshold
        │
        ▼
  scripts/retrain.py      When threshold crossed: rebuild graph with rating
                          signal → train new versioned model → register in
                          model_versions table → API hot-swaps to new version
```

---

## Model architecture

### HGAT (Heterogeneous Graph Attention Network)

The core model lives in `src/fitgraph/models/hgat.py`.

**Encoder (shared across node types)**

A deep nonlinear MLP is first applied to raw fused features for both garment
and outfit nodes:

```
Linear(896 → 512) → LayerNorm → GELU → Dropout
    → Linear(512 → hidden_dim) → LayerNorm → GELU → Dropout
```

The default `hidden_dim` is 256. This encoder produces a strong base
representation `h = encoder(x)` before any graph signal is applied.

**Heterogeneous GAT layers with residual connections**

`num_layers` (default 2) stacked `HeteroConv` layers follow. Each layer
contains two separate `GATConv` modules, one per edge direction:

- `('garment', 'in', 'outfit')` — garment → outfit
- `('outfit', 'contains', 'garment')` — outfit → garment

Each `GATConv` uses `num_heads=4` attention heads with `concat=False`
(mean-aggregation) and `add_self_loops=False`. After each layer, a residual
connection keeps gradients flowing:

```
h = h + dropout(ELU(GATConv_per_relation(h)))
```

**Cold-start / inductive path**

Because `add_self_loops=False` and the residual adds the pre-layer `h`, a
garment node with zero edges receives zero message-passing update — its
embedding after all layers equals `encoder(x)`. The method `embed_features(x)`
returns `L2_normalize(encoder(x))`, which is **identical** to what `forward`
would return for an isolated node. This means uploaded garments that are not in
the training graph can be embedded accurately using only their features, with
no representation gap.

**Final output**

Garment embeddings are L2-normalised before being returned, making cosine
similarity a natural compatibility metric.

### Type-aware embedding subspaces

The model in `src/fitgraph/models/type_aware.py` implements Vasileva et al.'s
type-aware embeddings (2018).

**Motivation:** a single shared embedding space represents "similar to" well,
but compatibility is about complementarity: tops pair with bottoms, not other
tops. A top and a bottom should score highly in the compatibility space even
though they look nothing alike.

**Implementation:** compatibility between an item of type A and an item of type
B is measured in a learned *type-pair-specific subspace*. The dataset's
`typespaces.p` file enumerates 66 semantic type-pair combinations. For each
pair, a learned non-negative mask (parameterised as `softplus` of a free
parameter) is applied element-wise to both shared embeddings before cosine
similarity is computed. Pairs whose types are not in the list fall back to a
single "general" subspace, giving 67 total subspaces.

`TypeAwareScorer` is jointly trained with the HGAT, so the subspace masks and
the GNN parameters are optimised together.

---

## Training

### InfoNCE contrastive loss

The loss is in `src/fitgraph/training/loss.py`. For each anchor garment, the
loss pushes its embedding close to its co-worn positives and away from
negatives. The type-aware variant (`type_aware_info_nce`) computes
anchor-positive and anchor-negative similarities via `TypeAwareScorer` in the
appropriate type-pair subspace, then applies cross-entropy over the logit
layout `[pos_score | neg_score_0, …, neg_score_{M-1}]` at each anchor.

Temperature (default 0.1) controls the sharpness of the distribution; lower
values produce stronger contrast.

### CLIP-mined hard negatives

Hard negatives (`src/fitgraph/training/negatives.py`) are items that are
visually similar to the anchor in CLIP space — small CLIP cosine distance —
but are *not* co-worn with it in any training outfit. These are the hardest
cases for the model: it must learn that visual similarity does not imply
compatibility. The mining procedure:

1. Compute CLIP cosine similarity from each anchor to all items in the local
   batch subgraph.
2. Mask out items that are co-worn with the anchor (forbidden set, built from
   the training co-occurrence map).
3. Select the top-k most CLIP-similar allowed items per anchor.

### Bounded shared negative pool

To keep peak memory predictable on Apple Silicon MPS, training uses a **bounded
shared negative pool** of at most `negative_pool_size` (default 256) items per
step. Hard-negative indices are deduplicated, then padded with random in-batch
items to reach the target pool size. All anchors in a step share the same pool,
so the peak intermediate tensor for `score_matrix` is `(B, M, dim)` rather than
`(B, B, dim)`.

### Mini-batch subgraph training

Each training step:

1. Samples a batch of TRAIN outfits.
2. Builds a small `HeteroData` subgraph containing only the garments and outfits
   in that batch.
3. Applies **neighbor (edge) dropout** — each edge in the subgraph is randomly
   dropped with probability `edge_dropout` (default 0.1). This forces the model
   to learn a robust inductive embedding path even when some outfit memberships
   are hidden.
4. Runs the HGAT forward pass on the subgraph.
5. Extracts co-worn positive pairs from the batch.
6. Mines hard negatives from CLIP features.
7. Computes and backpropagates `type_aware_info_nce`.

The co-occurrence map is built **only from training outfits**, so test-outfit
co-occurrences cannot influence which negatives are selected.

---

## Methodology and the leakage fix

**This section describes a real bug that was caught and corrected.**

An early version of the evaluation code ran the HGAT `forward` pass on a graph
that contained all outfit nodes, including the test-split outfits. When the
model computed embeddings for test garments, it performed message passing over
outfit nodes that included test co-occurrences. This gave the model direct
access to the co-occurrence signal it was supposed to be predicting, producing
artificially inflated AUC scores (~0.99).

The fix was straightforward: evaluation switched to the **inductive path** — all
test-item embeddings are produced exclusively via `model.embed_features(x)`,
which runs only the MLP encoder on the item's own features with no graph context
at all. Positive and negative pairs in the test set are scored by
`TypeAwareScorer` applied to these feature-only embeddings.

This is the honest and correct evaluation. An item that a user uploads at
inference time is also never in the training graph; it is embedded via
`embed_features`. Inductive evaluation ensures the metrics measure the same
capability that the deployed system actually exercises.

The neighbor dropout during training (described above) was added specifically to
supervise the inductive path: if the model only ever saw fully-connected outfit
subgraphs during training, the MLP encoder would be underutilised and the
inductive embeddings would be poor.

---

## Evaluation

The evaluation suite lives in `src/fitgraph/eval/`.

- **Compatibility AUC** — area under the ROC curve for binary compatible/not
  classification on the test split, using inductive embeddings only.
- **Fill-in-the-blank (FITB) accuracy** — given a partial outfit and a set of
  candidates, the model must select the item that actually belongs. Measures
  ranked compatibility discrimination.
- **Recall@K** — fraction of true positives recovered in the top-K retrieval
  results.
- **Qualitative outfit grids** — Pillow-rendered image grids of query garments
  and their top suggestions, saved as artifacts in `docs/assets/` for visual
  inspection.

Actual measured numbers from the training run are reported in the README
"Results" section. No numbers are stated here.

---

## Infrastructure

### Database (Postgres + pgvector)

The schema (`src/fitgraph/db/schema.sql`) includes:

- `users` — user accounts.
- `items` — catalog items with a `tsvector` tag column and a GIN index for
  full-text search.
- `item_embeddings` — a `vector(256)` column backed by an `ivfflat` index for
  approximate nearest-neighbour search via pgvector.
- `outfits`, `outfit_items` — saved outfit history with join table.
- `ratings` — user feedback (thumbs up/down) linked to items and model versions.
- `model_versions` — registry of trained checkpoints with metadata.

Non-trivial queries (`src/fitgraph/db/queries.py`) include outfit-history joins,
full-text tag search, and rating-volume aggregates used by the retrain trigger.

The pgvector retrieval client (`src/fitgraph/retrieval/pgvector_store.py`) uses
cosine distance (`<=>` operator) with an IVFFlat index and supports batch
upsert.

### Redis Streams feedback

Rating events are published to the stream `fitgraph:feedback` via Redis Streams
(`XADD`). A batch consumer uses `XREADGROUP` with consumer-group
`fitgraph:retrainers`, draining the pending-entry list first then new messages,
persisting each as a `Rating` row and acknowledging with `XACK`. Malformed
messages are still acknowledged to prevent infinite replay.

### FastAPI service

The inference API (`src/fitgraph/api/`) is a FastAPI application:

| Endpoint | Description |
|---|---|
| `GET /catalog/categories` | List all semantic categories with item counts |
| `GET /catalog/items` | Paginated catalog items filtered by category |
| `GET /items/{id}/outfit-suggestions` | Grouped per-category outfit suggestions for a seed item |
| `POST /compatibility` | Score compatibility between two items |
| `POST /outfits` | Save an outfit |
| `GET /outfits` | List a user's saved outfits |
| `POST /feedback` | Submit a rating (publishes to Redis Stream) |
| `GET /catalog/search` | Full-text search over item tags |
| `GET /healthz` | Health / readiness probe |

The `ModelService` in `api/serving.py` supports hot-swapping: it can load a new
versioned checkpoint at runtime without restarting the server. A lightweight
in-memory ring buffer (last 500 requests) tracks P99 latency, reported in the
`X-Response-Time-Ms` response header.

### Next.js frontend

The `web/` directory contains a Next.js 16 + TypeScript + Tailwind CSS
application with:

- **Browse home** — category navigation pills with item counts; responsive
  image-first item grid loaded via `GET /catalog/items`; "Load more"
  pagination. Each item card links to the outfit builder.
- **Outfit builder** (`/build/[itemId]`) — seed item pinned at the top;
  per-category suggestion sections fetched from
  `GET /items/{id}/outfit-suggestions`; each card shows the item image,
  a match-score badge, and thumbs up/down controls that call `POST /feedback`.
  One item per category can be selected; selected items appear in the sticky
  outfit tray.
- **Outfit tray** — sticky bottom bar showing the seed + selected items as
  thumbnails, a name input, and "Save outfit" which calls `POST /outfits`.
- **Saved outfits view** — calls `GET /outfits` to display a grid of outfit
  cards, each showing up to four item images and the outfit metadata.

### Docker Compose (local infrastructure)

`docker-compose.yml` runs two services for local development:

- `pgvector/pgvector:pg16` — Postgres with the pgvector extension, credentials
  `fitgraph/fitgraph`, database `fitgraph`.
- `redis:7-alpine` — Redis for the feedback stream.

Both services include healthchecks. No cloud accounts are needed to run the full
stack locally.

---

## Deferred production architecture (designed but not implemented)

The spec includes an intended AWS deployment that is **documented here for
completeness but not wired up**. Nothing in the current codebase connects to
AWS.

```
┌─────────────────────────────────────────────────────────────┐
│  Intended AWS deployment (not wired)                        │
│                                                             │
│  ECS Fargate task (FastAPI + model)                         │
│    └─ IAM role with least-privilege permissions             │
│                                                             │
│  S3 bucket                                                  │
│    └─ uploaded garment images                               │
│    └─ trained model checkpoints                             │
│                                                             │
│  RDS Postgres with pgvector extension                       │
│  ElastiCache Redis                                          │
│                                                             │
│  CloudWatch Logs for structured log aggregation             │
│                                                             │
│  AWS CDK (TypeScript) for infrastructure-as-code            │
│                                                             │
│  GitHub Actions deploy step (post-CI) → push image to ECR  │
│    → update ECS service                                     │
│                                                             │
│  Vercel deployment for the Next.js frontend                 │
└─────────────────────────────────────────────────────────────┘
```

The current GitHub Actions CI workflow (`ci.yml`) runs tests and lint only; it
has no deployment step. The Modal GPU training infrastructure (for faster
embedding generation and training runs) is also deferred.
