"""Phase 6 evaluation script — FitGraph v2 model.

Steps
-----
0. Export garment embeddings (HGAT forward pass) to
   data/models/v2/garment_embeddings.npz.
1. Compatibility AUC on disjoint/compatibility_test.txt.
2. Fill-in-the-blank accuracy on disjoint/fill_in_blank_test.json.
3. Recall@K (K=10, 30, 50) via leave-one-out over test outfits.
4. Qualitative grids saved to docs/assets/grid_{1..6}.png.
5. All numeric results written to data/models/v2/eval_results.json.
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

from fitgraph.config import resolve_device  # noqa: E402
from fitgraph.eval.grids import render_outfit_grid  # noqa: E402
from fitgraph.eval.metrics import accuracy, recall_at_k, roc_auc  # noqa: E402
from fitgraph.graph.builder import load_graph_bundle  # noqa: E402
from fitgraph.models.hgat import HGAT  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
POLYVORE_ROOT = _ROOT / "data" / "raw" / "polyvore-outfit-dataset" / "polyvore_outfits"
DISJOINT = POLYVORE_ROOT / "disjoint"
GRAPH_PT = _ROOT / "data" / "graph" / "graph.pt"
MODEL_DIR = _ROOT / "data" / "models" / "v2"
EMB_NPZ = MODEL_DIR / "garment_embeddings.npz"
RESULTS_JSON = MODEL_DIR / "eval_results.json"
GRIDS_DIR = _ROOT / "docs" / "assets"
IMAGES_DIR = POLYVORE_ROOT / "images"

RNG_SEED = 42


# ---------------------------------------------------------------------------
# Step 0 — export garment embeddings
# ---------------------------------------------------------------------------

def export_embeddings(device: str) -> tuple[list[str], np.ndarray]:
    """Load model + graph, run forward pass, save embeddings.npz."""
    if EMB_NPZ.exists():
        print("[Step 0] garment_embeddings.npz already exists — loading.")
        data = np.load(str(EMB_NPZ), allow_pickle=True)
        return list(data["ids"]), data["emb"].astype(np.float32)

    print("[Step 0] Exporting garment embeddings …")
    meta = json.loads((MODEL_DIR / "meta.json").read_text())

    model = HGAT(
        in_dim=meta["in_dim"],
        hidden_dim=meta["hidden_dim"],
        num_layers=meta["num_layers"],
        num_heads=meta["num_heads"],
    )
    state = torch.load(str(MODEL_DIR / "model.pt"), map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    bundle = load_graph_bundle(GRAPH_PT)
    graph = bundle.data.to(device)

    with torch.no_grad():
        emb = model.forward(graph)

    emb_np = emb.cpu().numpy().astype(np.float32)
    ids = bundle.garment_ids  # list[str]

    EMB_NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(EMB_NPZ), ids=np.array(ids), emb=emb_np)
    print(f"[Step 0] Saved {emb_np.shape[0]} embeddings → {EMB_NPZ}")
    return ids, emb_np


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


def cosine_sim_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return (N, M) cosine-similarity matrix. Both inputs are L2-normalised."""
    return a @ b.T


# ---------------------------------------------------------------------------
# Step 1 — Compatibility AUC
# ---------------------------------------------------------------------------

def eval_compatibility(
    garment_index: dict[str, int],
    emb: np.ndarray,
    ref_map: dict[tuple[str, str], str],
) -> tuple[float, int, int]:
    """Return (auc, evaluable, skipped)."""
    print("[Step 1] Compatibility AUC …")
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
            # Skip if any item not in graph
            if any(iid is None or iid not in garment_index for iid in item_ids):
                skipped += 1
                continue
            # Gather embeddings
            indices = [garment_index[iid] for iid in item_ids]  # type: ignore[index]
            vecs = emb[indices]  # (n_items, dim)
            # Mean pairwise cosine sim — vecs are already L2-normalised
            sim_mat = vecs @ vecs.T  # (n, n)
            n = len(indices)
            if n < 2:
                skipped += 1
                continue
            # Upper-triangle only (exclude diagonal)
            mask = np.triu(np.ones((n, n), dtype=bool), k=1)
            outfit_score = float(sim_mat[mask].mean())
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
) -> tuple[float, int, int]:
    """Return (accuracy, evaluable, skipped)."""
    print("[Step 2] Fill-in-the-blank accuracy …")
    fitb_path = DISJOINT / "fill_in_blank_test.json"
    data = json.loads(fitb_path.read_text())

    predictions: list[int] = []
    targets: list[int] = []
    skipped = 0

    for entry in data:
        question_refs = entry["question"]
        answer_refs = entry["answers"]

        # The correct answer is the one whose set_id matches the question outfit
        # Detect the question set_id from the first question ref
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

        # Find the true answer index: the candidate whose set_id matches q_set_id
        true_idx = None
        for i, aref in enumerate(answer_refs):
            a_set_id = aref.rsplit("_", 1)[0]
            if a_set_id == q_set_id:
                true_idx = i
                break
        if true_idx is None:
            skipped += 1
            continue

        # Compute score for each answer: mean cosine sim vs question items
        q_vecs = emb[[garment_index[iid] for iid in q_items]]  # type: ignore[index]
        q_mean = q_vecs.mean(axis=0)  # (dim,)
        # q_mean may not be unit-norm after averaging; normalise
        norm = float(np.linalg.norm(q_mean))
        if norm > 0:
            q_mean = q_mean / norm

        answer_scores = []
        for iid in a_items:
            a_vec = emb[garment_index[iid]]  # type: ignore[index]
            s = float(np.dot(q_mean, a_vec))
            answer_scores.append(s)

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

def eval_recall_at_k(
    garment_index: dict[str, int],
    emb: np.ndarray,
    bundle_outfit_ids: list[str],
    bundle_outfit_split: list[str],
) -> tuple[dict[int, float], int, int]:
    """Return ({K: recall}, evaluable, skipped)."""
    print("[Step 3] Recall@K …")
    # Build set_id → list[item_id] for test outfits in the graph
    # We have garment_ids (node order) and need the outfit→items mapping from graph
    # Use the test.json raw file for item lists
    raw_test = json.loads((DISJOINT / "test.json").read_text())
    set_items: dict[str, list[str]] = {}
    for entry in raw_test:
        set_id = str(entry["set_id"])
        item_ids = [str(it["item_id"]) for it in entry.get("items", [])]
        set_items[set_id] = item_ids

    # Collect test outfit set_ids from the graph bundle
    test_set_ids = {
        oid
        for oid, sp in zip(bundle_outfit_ids, bundle_outfit_split, strict=True)
        if sp == "test"
    }

    ks = [10, 30, 50]
    ranked_per_query: list[list[str]] = []
    relevant_per_query: list[str] = []
    skipped = 0

    # Pre-normalise all embeddings (already normalised from model, but just in case)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    emb_norm = emb / norms

    all_garment_ids = list(garment_index.keys())

    rng = random.Random(RNG_SEED)

    for set_id in sorted(test_set_ids):
        item_ids = set_items.get(set_id, [])
        # Filter to items in the graph
        valid_ids = [iid for iid in item_ids if iid in garment_index]
        if len(valid_ids) < 3:
            skipped += 1
            continue

        # Hold out one item at random
        held_out = rng.choice(valid_ids)
        context_ids = [iid for iid in valid_ids if iid != held_out]

        # Context mean embedding
        ctx_vecs = emb_norm[[garment_index[iid] for iid in context_ids]]
        ctx_mean = ctx_vecs.mean(axis=0)
        ctx_norm = np.linalg.norm(ctx_mean)
        if ctx_norm > 0:
            ctx_mean = ctx_mean / ctx_norm

        # Rank ALL garment nodes by cosine sim to ctx_mean
        sims = emb_norm @ ctx_mean  # (num_garments,)
        ranked_indices = np.argsort(-sims)  # descending
        ranked_ids = [all_garment_ids[i] for i in ranked_indices]

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
) -> None:
    """Render 6 qualitative outfit grids."""
    print("[Step 4] Rendering qualitative grids …")
    GRIDS_DIR.mkdir(parents=True, exist_ok=True)

    # Collect test outfit set_ids from graph
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

    # Gather candidate query items from test outfits that are in the graph
    candidate_items: list[str] = []
    for sid in test_set_ids:
        for iid in set_items.get(sid, []):
            if iid in garment_index:
                candidate_items.append(iid)
    candidate_items = list(set(candidate_items))

    rng = random.Random(RNG_SEED + 1)
    rng.shuffle(candidate_items)

    # Pre-normalise
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    emb_norm = emb / norms

    grids_rendered = 0
    for query_item_id in candidate_items:
        if grids_rendered >= 6:
            break
        img_path = IMAGES_DIR / f"{query_item_id}.jpg"
        if not img_path.exists():
            continue

        q_vec = emb_norm[garment_index[query_item_id]]
        sims = emb_norm @ q_vec
        ranked_indices = np.argsort(-sims)

        # Top-5 suggestions (excluding query itself)
        top_suggestions: list[str] = []
        top_scores: list[float] = []
        for idx in ranked_indices:
            cand_id = garment_ids_list[idx]
            if cand_id == query_item_id:
                continue
            top_suggestions.append(cand_id)
            top_scores.append(float(sims[idx]))
            if len(top_suggestions) >= 5:
                break

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
    device = resolve_device()
    print(f"Device: {device}")

    # --- Step 0: Export embeddings ---
    garment_ids_list, emb = export_embeddings(device)
    garment_index: dict[str, int] = {iid: i for i, iid in enumerate(garment_ids_list)}

    # Build reference map {(set_id, index_str): item_id} for test split
    ref_map = build_ref_map()

    # Load graph bundle for outfit split labels
    bundle = load_graph_bundle(GRAPH_PT)

    # --- Step 1: Compatibility AUC ---
    compat_auc, compat_evaluable, compat_skipped = eval_compatibility(
        garment_index, emb, ref_map
    )

    # --- Step 2: FITB accuracy ---
    fitb_acc, fitb_evaluable, fitb_skipped = eval_fitb(garment_index, emb, ref_map)

    # --- Step 3: Recall@K ---
    recall_results, recall_evaluable, recall_skipped = eval_recall_at_k(
        garment_index, emb, bundle.outfit_ids, bundle.outfit_split
    )

    # --- Step 4: Qualitative grids ---
    render_grids(
        garment_index,
        garment_ids_list,
        emb,
        bundle.outfit_ids,
        bundle.outfit_split,
    )

    # --- Step 5: Save results JSON ---
    results = {
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
