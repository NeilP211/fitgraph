"""Phase 6 evaluation script — FitGraph v4 model, honest inductive embeddings.

Embeddings used
---------------
data/models/v4/inductive_embeddings.npz — ALL 48,862 items embedded via
HGAT.embed_features() (pure feature-based, NO graph message passing).  This is
the leakage-free embedding that the deployed product computes for an uploaded
garment, and is safe to use for both candidates AND query items in every task.

Steps
-----
1. Compatibility AUC on disjoint/compatibility_test.txt.
2. Fill-in-the-blank accuracy on disjoint/fill_in_blank_test.json.
3. Recall@K (K=10, 30, 50) via leave-one-out over test outfits.
4. Qualitative grids saved to docs/assets/grid_{1..6}.png.
5. All numeric results written to data/models/v4/eval_results.json.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import torch

# ---------------------------------------------------------------------------
# Path setup — allow running as a script without installing the package
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from fitgraph.eval.grids import render_outfit_grid  # noqa: E402
from fitgraph.eval.metrics import accuracy, recall_at_k, roc_auc  # noqa: E402
from fitgraph.graph.builder import load_graph_bundle  # noqa: E402
from fitgraph.models.type_aware import TypeAwareScorer, TypeSpaceIndex  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
POLYVORE_ROOT = _ROOT / "data" / "raw" / "polyvore-outfit-dataset" / "polyvore_outfits"
DISJOINT = POLYVORE_ROOT / "disjoint"
GRAPH_PT = _ROOT / "data" / "graph" / "graph.pt"
MODEL_DIR = max(
    (
        d
        for d in (_ROOT / "data" / "models").glob("v*")
        if (d / "model.pt").exists() and (d / "inductive_embeddings.npz").exists()
    ),
    key=lambda d: int(d.name[1:]),
)
INDUCTIVE_NPZ = MODEL_DIR / "inductive_embeddings.npz"
MODEL_PT = MODEL_DIR / "model.pt"
TYPE_INDEX_JSON = MODEL_DIR / "type_index.json"
RESULTS_JSON = MODEL_DIR / "eval_results.json"
GRIDS_DIR = _ROOT / "docs" / "assets"
IMAGES_DIR = POLYVORE_ROOT / "images"

RNG_SEED = 42


# ---------------------------------------------------------------------------
# Type-aware scoring helpers
# ---------------------------------------------------------------------------


class TypeAwareEvaluator:
    """Wraps the trained TypeAwareScorer for vectorised numpy-side scoring.

    Loads the scorer state_dict from ``model.pt`` and the type system from
    ``type_index.json`` (both saved by the trainer in the model version dir).
    """

    def __init__(self, model_dir: Path, ids: list[str]) -> None:
        payload = json.loads((model_dir / "type_index.json").read_text())
        self.type_index = TypeSpaceIndex.from_dict(payload["type_index"])
        self.item_types: dict[str, str] = payload["item_types"]
        self.unknown_type: str = payload.get("unknown_type", "__unknown__")

        ckpt = torch.load(model_dir / "model.pt", map_location="cpu", weights_only=True)
        scorer_state = ckpt["scorer"]
        dim = int(scorer_state["masks"].shape[1])
        self.scorer = TypeAwareScorer(self.type_index.num_spaces, dim)
        self.scorer.load_state_dict(scorer_state)
        self.scorer.eval()

        # Per-row item type, parallel to the embedding rows.
        self._row_type: list[str] = [
            self.item_types.get(iid, self.unknown_type) for iid in ids
        ]
        self._pair_cache: dict[tuple[str, str], int] = {}

    def _space(self, ta: str, tb: str) -> int:
        key = (ta, tb) if ta <= tb else (tb, ta)
        s = self._pair_cache.get(key)
        if s is None:
            s = self.type_index.space_of(ta, tb)
            self._pair_cache[key] = s
        return s

    def score_index_pairs(
        self, emb: np.ndarray, a_idx: list[int], b_idx: list[int]
    ) -> np.ndarray:
        """Type-aware similarity for paired index lists -> ``(B,)`` numpy array."""
        space_ids = torch.tensor(
            [
                self._space(self._row_type[a], self._row_type[b])
                for a, b in zip(a_idx, b_idx, strict=True)
            ],
            dtype=torch.long,
        )
        ea = torch.from_numpy(emb[a_idx].astype(np.float32))
        eb = torch.from_numpy(emb[b_idx].astype(np.float32))
        with torch.no_grad():
            return self.scorer.score_pairs(ea, eb, space_ids).numpy()

    def score_one_vs_many(
        self, emb: np.ndarray, anchor_idx: int, cand_idx: list[int]
    ) -> np.ndarray:
        """Type-aware similarity of one anchor vs many candidates -> ``(C,)``."""
        space_ids = torch.tensor(
            [[self._space(self._row_type[anchor_idx], self._row_type[c])
              for c in cand_idx]],
            dtype=torch.long,
        )  # (1, C)
        anchor = torch.from_numpy(emb[anchor_idx : anchor_idx + 1].astype(np.float32))
        cands = torch.from_numpy(emb[cand_idx].astype(np.float32))
        with torch.no_grad():
            return self.scorer.score_matrix(anchor, cands, space_ids).numpy()[0]


# ---------------------------------------------------------------------------
# Step 0 — load honest inductive embeddings
# ---------------------------------------------------------------------------

def load_embeddings() -> tuple[list[str], np.ndarray]:
    """Load pre-built inductive (feature-only) embeddings for all items."""
    print("[Step 0] Loading inductive_embeddings.npz …")
    data = np.load(str(INDUCTIVE_NPZ), allow_pickle=True)
    ids: list[str] = list(data["ids"])
    emb: np.ndarray = data["emb"].astype(np.float32)
    # L2-normalise so cosine sim == dot product
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    emb = emb / norms
    print(f"[Step 0] Loaded {emb.shape[0]} embeddings, dim={emb.shape[1]}")
    return ids, emb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_ref_map() -> dict[tuple[str, str], str]:
    """Build {(set_id, index_str): item_id} from raw disjoint/test.json."""
    raw = json.loads((DISJOINT / "test.json").read_text())
    ref_map: dict[tuple[str, str], str] = {}
    for entry in raw:
        set_id = str(entry["set_id"])
        for it in entry.get("items", []):
            idx_str = str(it["index"])
            ref_map[(set_id, idx_str)] = str(it["item_id"])
    return ref_map


def resolve_ref(ref: str, ref_map: dict[tuple[str, str], str]) -> str | None:
    """Resolve '<set_id>_<index>' → item_id, or None if not in test split."""
    parts = ref.rsplit("_", 1)
    if len(parts) != 2:
        return None
    set_id, idx = parts
    return ref_map.get((set_id, idx))


# ---------------------------------------------------------------------------
# Step 1 — Compatibility AUC
# ---------------------------------------------------------------------------

def eval_compatibility(
    garment_index: dict[str, int],
    emb: np.ndarray,
    ref_map: dict[tuple[str, str], str],
    scorer: TypeAwareEvaluator,
) -> tuple[float, int, int]:
    """Return (auc, evaluable, skipped).

    Outfit score = mean type-aware pairwise score over all member pairs, each
    pair scored in its own type-pair subspace.
    """
    print("[Step 1] Compatibility AUC (type-aware) …")
    compat_path = DISJOINT / "compatibility_test.txt"
    scores: list[float] = []
    labels: list[int] = []
    skipped = 0

    with compat_path.open() as fh:
        for line in fh:
            parts = line.strip().split()
            if not parts:
                continue
            label = int(parts[0])
            refs = parts[1:]
            item_ids = [resolve_ref(r, ref_map) for r in refs]
            # Skip if any item not covered by inductive embeddings
            if any(iid is None or iid not in garment_index for iid in item_ids):
                skipped += 1
                continue
            indices = [garment_index[iid] for iid in item_ids]  # type: ignore[index]
            n = len(indices)
            if n < 2:
                skipped += 1
                continue
            # Mean type-aware pairwise score over all member pairs.
            a_idx: list[int] = []
            b_idx: list[int] = []
            for i in range(n):
                for j in range(i + 1, n):
                    a_idx.append(indices[i])
                    b_idx.append(indices[j])
            pair_scores = scorer.score_index_pairs(emb, a_idx, b_idx)
            outfit_score = float(pair_scores.mean())
            scores.append(outfit_score)
            labels.append(label)

    evaluable = len(scores)
    auc = roc_auc(scores, labels)
    print(f"[Step 1] AUC={auc:.4f}  evaluable={evaluable}  skipped={skipped}")
    return auc, evaluable, skipped


# ---------------------------------------------------------------------------
# Step 2 — Fill-in-the-blank accuracy
# ---------------------------------------------------------------------------

def eval_fitb(
    garment_index: dict[str, int],
    emb: np.ndarray,
    ref_map: dict[tuple[str, str], str],
    scorer: TypeAwareEvaluator,
) -> tuple[float, int, int]:
    """Return (accuracy, evaluable, skipped).

    Each candidate answer is scored as the mean type-aware score of that
    answer against every question item (each pair in its type-pair subspace).
    """
    print("[Step 2] Fill-in-the-blank accuracy (type-aware) …")
    fitb_path = DISJOINT / "fill_in_blank_test.json"
    data = json.loads(fitb_path.read_text())

    predictions: list[int] = []
    targets: list[int] = []
    skipped = 0

    for entry in data:
        question_refs = entry["question"]
        answer_refs = entry["answers"]

        # The correct answer is the candidate whose set_id matches the question outfit
        q_set_id = question_refs[0].rsplit("_", 1)[0]

        # Resolve question items
        q_items = [resolve_ref(r, ref_map) for r in question_refs]
        if any(iid is None or iid not in garment_index for iid in q_items):
            skipped += 1
            continue

        # Resolve answer items
        a_items = [resolve_ref(r, ref_map) for r in answer_refs]
        if any(iid is None or iid not in garment_index for iid in a_items):
            skipped += 1
            continue

        # True answer: the candidate whose set_id matches the question outfit
        true_idx = None
        for i, aref in enumerate(answer_refs):
            a_set_id = aref.rsplit("_", 1)[0]
            if a_set_id == q_set_id:
                true_idx = i
                break
        if true_idx is None:
            skipped += 1
            continue

        # Score each answer: mean type-aware score against every question item.
        q_indices = [garment_index[iid] for iid in q_items]  # type: ignore[index]
        answer_scores: list[float] = []
        for iid in a_items:
            a_i = garment_index[iid]  # type: ignore[index]
            pair_scores = scorer.score_one_vs_many(emb, a_i, q_indices)
            answer_scores.append(float(pair_scores.mean()))

        pred_idx = int(np.argmax(answer_scores))
        predictions.append(pred_idx)
        targets.append(true_idx)

    evaluable = len(predictions)
    acc = accuracy(predictions, targets)
    print(f"[Step 2] Accuracy={acc:.4f}  evaluable={evaluable}  skipped={skipped}")
    return acc, evaluable, skipped


# ---------------------------------------------------------------------------
# Step 3 — Recall@K
# ---------------------------------------------------------------------------

def _rank_by_type_aware(
    emb: np.ndarray,
    context_idx: list[int],
    scorer: TypeAwareEvaluator,
) -> np.ndarray:
    """Rank ALL catalog items by mean type-aware score against the context.

    For each context item, score every catalog item against it in the relevant
    type-pair subspace; the candidate score is the mean over context items.
    Returns catalog indices sorted descending by score.
    """
    all_idx = list(range(emb.shape[0]))
    score_sum = np.zeros(emb.shape[0], dtype=np.float64)
    for ctx_i in context_idx:
        score_sum += scorer.score_one_vs_many(emb, ctx_i, all_idx)
    mean_scores = score_sum / max(1, len(context_idx))
    return np.argsort(-mean_scores)


def eval_recall_at_k(
    garment_index: dict[str, int],
    garment_ids_list: list[str],
    emb: np.ndarray,
    bundle_outfit_ids: list[str],
    bundle_outfit_split: list[str],
    scorer: TypeAwareEvaluator,
) -> tuple[dict[int, float], int, int]:
    """Return ({K: recall}, evaluable, skipped)."""
    print("[Step 3] Recall@K (type-aware) …")

    raw_test = json.loads((DISJOINT / "test.json").read_text())
    set_items: dict[str, list[str]] = {}
    for entry in raw_test:
        set_id = str(entry["set_id"])
        item_ids = [str(it["item_id"]) for it in entry.get("items", [])]
        set_items[set_id] = item_ids

    # Test outfits from the graph bundle
    test_set_ids = {
        oid
        for oid, sp in zip(bundle_outfit_ids, bundle_outfit_split, strict=True)
        if sp == "test"
    }

    ks = [10, 30, 50]
    ranked_per_query: list[list[str]] = []
    relevant_per_query: list[str] = []
    skipped = 0

    rng = random.Random(RNG_SEED)

    for set_id in sorted(test_set_ids):
        item_ids = set_items.get(set_id, [])
        # Filter to items covered by inductive embeddings
        valid_ids = [iid for iid in item_ids if iid in garment_index]
        if len(valid_ids) < 3:
            skipped += 1
            continue

        # Hold out one item at random
        held_out = rng.choice(valid_ids)
        context_ids = [iid for iid in valid_ids if iid != held_out]

        # Rank ALL items by mean type-aware score against the context items.
        context_idx = [garment_index[iid] for iid in context_ids]
        ranked_indices = _rank_by_type_aware(emb, context_idx, scorer)
        ranked_ids = [garment_ids_list[i] for i in ranked_indices]

        ranked_per_query.append(ranked_ids)
        relevant_per_query.append(held_out)

    evaluable = len(ranked_per_query)
    results: dict[int, float] = {}
    for k in ks:
        r_at_k = recall_at_k(ranked_per_query, relevant_per_query, k)
        results[k] = r_at_k
        print(f"[Step 3] Recall@{k:<3d} = {r_at_k:.4f}")
    print(f"[Step 3] evaluable={evaluable}  skipped={skipped}")
    return results, evaluable, skipped


# ---------------------------------------------------------------------------
# Step 4 — Qualitative grids
# ---------------------------------------------------------------------------

def render_grids(
    garment_index: dict[str, int],
    garment_ids_list: list[str],
    emb: np.ndarray,
    bundle_outfit_ids: list[str],
    bundle_outfit_split: list[str],
    scorer: TypeAwareEvaluator,
) -> None:
    """Render 6 qualitative outfit grids ranked by type-aware compatibility."""
    print("[Step 4] Rendering qualitative grids …")
    GRIDS_DIR.mkdir(parents=True, exist_ok=True)

    raw_test = json.loads((DISJOINT / "test.json").read_text())
    set_items: dict[str, list[str]] = {}
    for entry in raw_test:
        set_id = str(entry["set_id"])
        item_ids = [str(it["item_id"]) for it in entry.get("items", [])]
        set_items[set_id] = item_ids

    test_set_ids = [
        oid
        for oid, sp in zip(bundle_outfit_ids, bundle_outfit_split, strict=True)
        if sp == "test"
    ]

    # Gather candidate query items from test outfits that are covered by inductive emb
    candidate_items: list[str] = []
    for sid in test_set_ids:
        for iid in set_items.get(sid, []):
            if iid in garment_index:
                candidate_items.append(iid)
    candidate_items = list(set(candidate_items))

    rng = random.Random(RNG_SEED + 1)
    rng.shuffle(candidate_items)

    grids_rendered = 0
    for query_item_id in candidate_items:
        if grids_rendered >= 6:
            break
        img_path = IMAGES_DIR / f"{query_item_id}.jpg"
        if not img_path.exists():
            continue

        query_idx = garment_index[query_item_id]
        all_idx = list(range(emb.shape[0]))
        sims = scorer.score_one_vs_many(emb, query_idx, all_idx)  # (num_items,)
        ranked_indices = np.argsort(-sims)

        # Top-5 suggestions (excluding query itself)
        top_suggestions: list[str] = []
        top_scores: list[float] = []
        for idx in ranked_indices:
            cand_id = garment_ids_list[idx]
            if cand_id == query_item_id:
                continue
            cand_img = IMAGES_DIR / f"{cand_id}.jpg"
            if not cand_img.exists():
                continue
            top_suggestions.append(cand_id)
            top_scores.append(float(sims[idx]))
            if len(top_suggestions) >= 5:
                break

        if len(top_suggestions) < 5:
            continue

        sug_paths = [IMAGES_DIR / f"{iid}.jpg" for iid in top_suggestions]
        out_file = GRIDS_DIR / f"grid_{grids_rendered + 1}.png"

        render_outfit_grid(img_path, sug_paths, out_file, scores=top_scores)
        print(f"[Step 4] Saved {out_file}")
        grids_rendered += 1

    if grids_rendered < 6:
        print(
            f"[Step 4] Warning: only {grids_rendered}/6 grids rendered"
            " (not enough test items with images)."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # --- Step 0: Load honest inductive embeddings ---
    garment_ids_list, emb = load_embeddings()
    garment_index: dict[str, int] = {iid: i for i, iid in enumerate(garment_ids_list)}

    # Build reference map {(set_id, index_str): item_id} for test split
    ref_map = build_ref_map()

    # Load graph bundle for outfit split labels
    bundle = load_graph_bundle(GRAPH_PT)

    # Load the trained type-aware scorer + type system from the model dir.
    print("[Step 0] Loading type-aware scorer + type index …")
    scorer = TypeAwareEvaluator(MODEL_DIR, garment_ids_list)

    # --- Step 1: Compatibility AUC ---
    compat_auc, compat_evaluable, compat_skipped = eval_compatibility(
        garment_index, emb, ref_map, scorer
    )

    # --- Step 2: FITB accuracy ---
    fitb_acc, fitb_evaluable, fitb_skipped = eval_fitb(
        garment_index, emb, ref_map, scorer
    )

    # --- Step 3: Recall@K ---
    recall_results, recall_evaluable, recall_skipped = eval_recall_at_k(
        garment_index, garment_ids_list, emb, bundle.outfit_ids,
        bundle.outfit_split, scorer
    )

    # --- Step 4: Qualitative grids ---
    render_grids(
        garment_index,
        garment_ids_list,
        emb,
        bundle.outfit_ids,
        bundle.outfit_split,
        scorer,
    )

    # --- Step 5: Save results JSON ---
    results = {
        "model": MODEL_DIR.name,
        "embeddings": "inductive (feature-only, no graph message passing)",
        "scoring": "type-aware (per type-pair subspace)",
        "compatibility_auc": compat_auc,
        "compatibility_evaluable": compat_evaluable,
        "compatibility_skipped": compat_skipped,
        "fitb_accuracy": fitb_acc,
        "fitb_evaluable": fitb_evaluable,
        "fitb_skipped": fitb_skipped,
        "recall_at_10": recall_results[10],
        "recall_at_30": recall_results[30],
        "recall_at_50": recall_results[50],
        "recall_evaluable": recall_evaluable,
        "recall_skipped": recall_skipped,
    }
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(results, indent=2))
    print(f"\n[Done] Results written to {RESULTS_JSON}")
    print("\n========== SUMMARY ==========")
    print(
        f"  Compatibility AUC  : {compat_auc:.4f}"
        f"  ({compat_evaluable} evaluable, {compat_skipped} skipped)"
    )
    print(
        f"  FITB Accuracy      : {fitb_acc:.4f}"
        f"  ({fitb_evaluable} evaluable, {fitb_skipped} skipped)"
    )
    print(f"  Recall@10          : {recall_results[10]:.4f}")
    print(f"  Recall@30          : {recall_results[30]:.4f}")
    print(f"  Recall@50          : {recall_results[50]:.4f}")
    print(f"  (Recall evaluable={recall_evaluable}, skipped={recall_skipped})")
    print("==============================")


if __name__ == "__main__":
    main()
