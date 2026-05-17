"""Build and save item embeddings for the Polyvore dataset.

Usage
-----
    # Default: subset of 5 000 outfits (controlled by settings.subset_outfits)
    python scripts/build_embeddings.py

    # Full dataset
    python scripts/build_embeddings.py --full

Output
------
    data/embeddings/items.npz  — arrays: ids, clip_emb, text_emb, fused
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src/ is on the path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from fitgraph.config import settings
from fitgraph.data.polyvore import load_item_metadata
from fitgraph.data.splits import load_splits
from fitgraph.embeddings import ClipEncoder, TextEncoder, fuse


def main(use_full: bool = False) -> None:
    polyvore_root = settings.raw_dir / "polyvore-outfit-dataset" / "polyvore_outfits"
    images_dir = polyvore_root / "images"
    metadata_path = polyvore_root / "polyvore_item_metadata.json"

    # ── 1. Load splits ────────────────────────────────────────────────────────
    subset = None if use_full else settings.subset_outfits
    print(f"Loading splits (subset_outfits={subset!r}) …")
    splits = load_splits(polyvore_root, subset_outfits=subset)

    # ── 2. Collect unique item ids across all splits ──────────────────────────
    unique_item_ids: set[str] = set()
    for outfits in splits.values():
        for outfit in outfits:
            unique_item_ids.update(outfit.item_ids)
    print(f"Unique item IDs across all splits: {len(unique_item_ids)}")

    # ── 3. Load metadata, filter to items with existing images ───────────────
    print("Loading item metadata …")
    all_items = load_item_metadata(metadata_path, images_dir)

    items_to_encode = []
    n_missing = 0
    for item_id in sorted(unique_item_ids):
        item = all_items.get(item_id)
        if item is None:
            n_missing += 1
            continue
        if not item.image_path.exists():
            n_missing += 1
            continue
        items_to_encode.append(item)

    print(f"Items to encode: {len(items_to_encode)}  |  skipped (missing image/meta): {n_missing}")

    if not items_to_encode:
        print("ERROR: No items to encode. Check that the dataset is in place.")
        sys.exit(1)

    # ── 4. Encode images with CLIP ────────────────────────────────────────────
    print("Initialising CLIP encoder …")
    clip_enc = ClipEncoder()
    image_paths = [item.image_path for item in items_to_encode]
    print(f"Encoding {len(image_paths)} images …")
    clip_emb = clip_enc.encode_images(image_paths, batch_size=64)

    # ── 5. Encode text with sentence-transformers ────────────────────────────
    print("Initialising text encoder …")
    text_enc = TextEncoder()
    texts = [f"{item.title}. {item.description}".strip() for item in items_to_encode]
    print(f"Encoding {len(texts)} text strings …")
    text_emb = text_enc.encode(texts, batch_size=128)

    # ── 6. Fuse ───────────────────────────────────────────────────────────────
    print("Fusing embeddings …")
    fused_emb = fuse(clip_emb, text_emb)

    # ── 7. Save ───────────────────────────────────────────────────────────────
    settings.embeddings_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.embeddings_dir / "items.npz"

    ids_array = np.array([item.id for item in items_to_encode])
    np.savez(
        out_path,
        ids=ids_array,
        clip_emb=clip_emb,
        text_emb=text_emb,
        fused=fused_emb,
    )

    # ── 8. Report ─────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"Items embedded  : {len(items_to_encode)}")
    print(f"Items skipped   : {n_missing}")
    print(f"Output path     : {out_path.resolve()}")
    print(f"clip_emb shape  : {clip_emb.shape}")
    print(f"text_emb shape  : {text_emb.shape}")
    print(f"fused shape     : {fused_emb.shape}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FitGraph item embeddings.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use the full dataset instead of the configured subset.",
    )
    args = parser.parse_args()
    main(use_full=args.full)
