"""CLI script: download Polyvore dataset and print a summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src/ is on the path when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fitgraph.config import settings
from fitgraph.data.download import download_polyvore
from fitgraph.data.splits import load_splits


def main() -> None:
    print("=" * 60)
    print("FitGraph — Polyvore dataset download")
    print("=" * 60)

    polyvore_outfits_dir = download_polyvore(settings.raw_dir)
    print(f"\nDataset root: {polyvore_outfits_dir}\n")

    # Load splits and print outfit counts
    splits = load_splits(polyvore_outfits_dir)
    for split_name, outfits in splits.items():
        print(f"  {split_name:>6} outfits: {len(outfits):>6}")

    # Count items from metadata
    # Try the known path first, then glob
    metadata_path = polyvore_outfits_dir / "polyvore_item_metadata.json"
    if not metadata_path.exists():
        matches = list(polyvore_outfits_dir.rglob("polyvore_item_metadata.json"))
        if matches:
            metadata_path = matches[0]

    if metadata_path.exists():
        with metadata_path.open() as fh:
            metadata = json.load(fh)
        n_items = len(metadata)
        print(f"\n  Total items in metadata: {n_items:>8}")
    else:
        print("\n  (Could not locate polyvore_item_metadata.json for item count)")

    print("\nDone.")


if __name__ == "__main__":
    main()
