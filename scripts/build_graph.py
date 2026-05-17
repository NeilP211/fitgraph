"""Build the bipartite hetero graph for FitGraph and write it to data/graph/graph.pt.

Usage
-----
# Default subset (settings.subset_outfits = 5000):
    python scripts/build_graph.py

# Full dataset:
    python scripts/build_graph.py --full
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from fitgraph.config import settings
from fitgraph.data.splits import load_splits
from fitgraph.graph.builder import build_hetero_graph, save_graph_bundle

POLYVORE_ROOT = settings.raw_dir / "polyvore-outfit-dataset" / "polyvore_outfits"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FitGraph hetero graph")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use the full dataset instead of the configured subset.",
    )
    args = parser.parse_args()

    use_full: bool = args.full or settings.use_full
    subset: int | None = None if use_full else settings.subset_outfits

    print(f"[build_graph] mode={'full' if use_full else f'subset({subset})'}")

    # ------------------------------------------------------------------
    # 1. Load splits
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    print(f"[build_graph] Loading splits from {POLYVORE_ROOT} …")
    splits = load_splits(POLYVORE_ROOT, subset_outfits=subset)
    for split_name, outfits in splits.items():
        print(f"  {split_name}: {len(outfits)} outfits")

    # ------------------------------------------------------------------
    # 2. Load embeddings
    # ------------------------------------------------------------------
    emb_path = settings.embeddings_dir / "items.npz"
    print(f"[build_graph] Loading embeddings from {emb_path} …")
    npz = np.load(emb_path)
    ids: np.ndarray = npz["ids"]       # (N,) str
    fused: np.ndarray = npz["fused"]   # (N, 896) float32
    item_embeddings: dict[str, np.ndarray] = {
        str(item_id): fused[i] for i, item_id in enumerate(ids)
    }
    print(f"  {len(item_embeddings)} items with embeddings loaded")

    # ------------------------------------------------------------------
    # 3. Build graph
    # ------------------------------------------------------------------
    print("[build_graph] Building hetero graph …")
    bundle = build_hetero_graph(splits, item_embeddings)

    # ------------------------------------------------------------------
    # 4. Print stats
    # ------------------------------------------------------------------
    num_garments = len(bundle.garment_ids)
    num_outfits = len(bundle.outfit_ids)
    num_edges = bundle.data["garment", "in", "outfit"].edge_index.shape[1]
    dropped = bundle.data["outfit"].num_dropped

    print("\n[build_graph] Graph stats")
    print(f"  Garment nodes : {num_garments:,}")
    print(f"  Outfit nodes  : {num_outfits:,}  (dropped: {dropped:,})")

    for split_name in ("train", "valid", "test"):
        count = sum(1 for s in bundle.outfit_split if s == split_name)
        print(f"    {split_name:5s}  : {count:,} outfits")

    print(f"  Edges (garment→outfit)  : {num_edges:,}")
    print(f"  Edges (outfit→garment)  : {num_edges:,}  [reverse]")

    # ------------------------------------------------------------------
    # 5. Save
    # ------------------------------------------------------------------
    out_path = settings.graph_dir / "graph.pt"
    print(f"\n[build_graph] Saving to {out_path} …")
    save_graph_bundle(bundle, out_path)

    elapsed = time.perf_counter() - t0
    print(f"[build_graph] Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
