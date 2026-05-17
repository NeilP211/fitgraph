"""Kaggle download helper for the Polyvore Outfits dataset."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path


_KAGGLE_SLUG = "yiitcandeime/polyvore"
_SENTINEL = "polyvore-outfit-dataset/polyvore_outfits/disjoint/train.json"


def download_polyvore(dest: Path) -> Path:
    """Download and unzip the Polyvore Outfits dataset into *dest*.

    Idempotent: if the sentinel file already exists the download is skipped.

    Parameters
    ----------
    dest:
        Destination directory (e.g. ``settings.raw_dir`` = ``data/raw``).

    Returns
    -------
    Path
        The path to the ``polyvore_outfits`` directory.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    sentinel = dest / _SENTINEL
    polyvore_outfits_dir = dest / "polyvore-outfit-dataset" / "polyvore_outfits"

    if sentinel.exists():
        print(f"Dataset already present at {polyvore_outfits_dir} — skipping download.")
        return polyvore_outfits_dir

    # Set KAGGLE_KEY from KAGGLE_API_TOKEN before importing kaggle
    api_token = os.environ.get("KAGGLE_API_TOKEN")
    if api_token:
        os.environ.setdefault("KAGGLE_KEY", api_token)

    # Import here so the env var is set first
    from kaggle.api.kaggle_api_extended import KaggleApi  # noqa: PLC0415

    api = KaggleApi()
    api.authenticate()

    print(f"Downloading {_KAGGLE_SLUG} → {dest} ...")
    api.dataset_download_files(
        _KAGGLE_SLUG,
        path=str(dest),
        unzip=False,
        quiet=False,
    )

    # Find and unzip any downloaded zip files
    for zip_path in dest.glob("*.zip"):
        print(f"Unzipping {zip_path} ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        zip_path.unlink()
        print(f"Removed {zip_path.name}")

    if not sentinel.exists():
        # Try to find polyvore_outfits by globbing in case directory nesting differs
        matches = list(dest.rglob("polyvore_item_metadata.json"))
        if matches:
            polyvore_outfits_dir = matches[0].parent
            print(f"Found polyvore_outfits at {polyvore_outfits_dir}")
        else:
            raise FileNotFoundError(
                f"Expected sentinel {sentinel} not found after download/unzip. "
                f"Check the contents of {dest}"
            )

    return polyvore_outfits_dir
