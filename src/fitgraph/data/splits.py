"""Split loading and subsetting for the Polyvore Outfits disjoint splits."""

from __future__ import annotations

import math
import random
from pathlib import Path

from fitgraph.data.polyvore import Outfit, load_outfits


def load_splits(
    polyvore_root: Path,
    subset_outfits: int | None = None,
    seed: int = 42,
) -> dict[str, list[Outfit]]:
    """Load train/valid/test splits from ``polyvore_root/disjoint/``.

    The disjoint folder already provides leakage-free splits; this function
    reads them as-is and optionally subsets for fast iteration.

    Parameters
    ----------
    polyvore_root:
        Path to the ``polyvore_outfits`` directory (contains ``disjoint/``).
    subset_outfits:
        If given, sample this many outfits from the train split and scale
        valid/test proportionally. If >= number of available outfits, all
        outfits are returned. ``None`` returns the full splits.
    seed:
        Random seed for deterministic sampling.

    Returns
    -------
    dict with keys ``"train"``, ``"valid"``, ``"test"`` mapping to lists of
    :class:`~fitgraph.data.polyvore.Outfit`.

    Raises
    ------
    AssertionError
        If any set_id appears in more than one split (dataset integrity check).
    """
    disjoint = polyvore_root / "disjoint"
    train = load_outfits(disjoint / "train.json")
    valid = load_outfits(disjoint / "valid.json")
    test = load_outfits(disjoint / "test.json")

    # --- Integrity assertion: no set_id should appear in more than one split ---
    train_ids = {o.id for o in train}
    valid_ids = {o.id for o in valid}
    test_ids = {o.id for o in test}
    assert train_ids & valid_ids == set(), "Dataset integrity error: train/valid set_id overlap"
    assert train_ids & test_ids == set(), "Dataset integrity error: train/test set_id overlap"
    assert valid_ids & test_ids == set(), "Dataset integrity error: valid/test set_id overlap"

    if subset_outfits is None:
        return {"train": train, "valid": valid, "test": test}

    n_train = len(train)
    n_valid = len(valid)
    n_test = len(test)

    # If subset_outfits >= available, return everything
    if subset_outfits >= n_train:
        return {"train": train, "valid": valid, "test": test}

    # Compute scale factor from train, apply proportionally to valid/test
    scale = subset_outfits / n_train

    rng = random.Random(seed)

    # Sample train
    sampled_train = rng.sample(train, subset_outfits)

    # Scale valid/test — always keep at least 1 if the split is non-empty
    n_valid_sub = max(1, math.floor(n_valid * scale)) if n_valid else 0
    n_test_sub = max(1, math.floor(n_test * scale)) if n_test else 0

    sampled_valid = rng.sample(valid, min(n_valid_sub, n_valid))
    sampled_test = rng.sample(test, min(n_test_sub, n_test))

    return {"train": sampled_train, "valid": sampled_valid, "test": sampled_test}
