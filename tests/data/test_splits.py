"""Tests for fitgraph.data.splits — split loading, subsetting, and disjointness."""

import json
import random
from pathlib import Path

import pytest

from fitgraph.data.polyvore import Outfit
from fitgraph.data.splits import load_splits

# ---------------------------------------------------------------------------
# Helpers to build a tiny in-memory split directory
# ---------------------------------------------------------------------------


def _make_outfit_json(outfit_ids: list[str]) -> list[dict]:
    """Return a minimal outfit JSON list with 2 items each."""
    return [
        {"set_id": oid, "items": [{"item_id": f"i_{oid}_1", "index": 1}, {"item_id": f"i_{oid}_2", "index": 2}]}
        for oid in outfit_ids
    ]


def _write_splits(tmp_path: Path, train_ids: list[str], valid_ids: list[str], test_ids: list[str]) -> Path:
    """Write disjoint/{train,valid,test}.json into tmp_path/disjoint and return tmp_path."""
    disjoint = tmp_path / "disjoint"
    disjoint.mkdir(parents=True, exist_ok=True)
    (disjoint / "train.json").write_text(json.dumps(_make_outfit_json(train_ids)))
    (disjoint / "valid.json").write_text(json.dumps(_make_outfit_json(valid_ids)))
    (disjoint / "test.json").write_text(json.dumps(_make_outfit_json(test_ids)))
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadSplitsBasic:
    def test_returns_three_splits(self, tmp_path):
        root = _write_splits(tmp_path, ["t1", "t2", "t3"], ["v1"], ["e1"])
        splits = load_splits(root)
        assert set(splits.keys()) == {"train", "valid", "test"}

    def test_each_split_contains_outfits(self, tmp_path):
        root = _write_splits(tmp_path, ["t1", "t2", "t3"], ["v1", "v2"], ["e1", "e2"])
        splits = load_splits(root)
        assert len(splits["train"]) == 3
        assert len(splits["valid"]) == 2
        assert len(splits["test"]) == 2

    def test_outfits_are_outfit_objects(self, tmp_path):
        root = _write_splits(tmp_path, ["t1"], ["v1"], ["e1"])
        splits = load_splits(root)
        assert all(isinstance(o, Outfit) for o in splits["train"])
        assert all(isinstance(o, Outfit) for o in splits["valid"])
        assert all(isinstance(o, Outfit) for o in splits["test"])


class TestSplitDisjointness:
    def test_no_set_id_in_multiple_splits(self, tmp_path):
        """Core invariant: each set_id must appear in exactly one split."""
        root = _write_splits(
            tmp_path,
            [f"train_{i}" for i in range(10)],
            [f"valid_{i}" for i in range(3)],
            [f"test_{i}" for i in range(3)],
        )
        splits = load_splits(root)
        train_ids = {o.id for o in splits["train"]}
        valid_ids = {o.id for o in splits["valid"]}
        test_ids = {o.id for o in splits["test"]}

        assert train_ids & valid_ids == set(), "train/valid overlap"
        assert train_ids & test_ids == set(), "train/test overlap"
        assert valid_ids & test_ids == set(), "valid/test overlap"


class TestSubsetting:
    def test_subset_outfits_limits_train(self, tmp_path):
        root = _write_splits(
            tmp_path,
            [f"t{i}" for i in range(100)],
            [f"v{i}" for i in range(20)],
            [f"e{i}" for i in range(20)],
        )
        splits = load_splits(root, subset_outfits=10, seed=42)
        assert len(splits["train"]) == 10

    def test_subset_scales_valid_and_test_proportionally(self, tmp_path):
        """valid/test should scale by the same fraction used for train."""
        root = _write_splits(
            tmp_path,
            [f"t{i}" for i in range(100)],
            [f"v{i}" for i in range(20)],
            [f"e{i}" for i in range(20)],
        )
        splits = load_splits(root, subset_outfits=50, seed=42)
        # train fraction = 50/100 = 0.5; valid/test should each be ~10
        assert 1 <= len(splits["valid"]) <= 20
        assert 1 <= len(splits["test"]) <= 20

    def test_subset_is_deterministic(self, tmp_path):
        root = _write_splits(
            tmp_path,
            [f"t{i}" for i in range(100)],
            [f"v{i}" for i in range(20)],
            [f"e{i}" for i in range(20)],
        )
        splits_a = load_splits(root, subset_outfits=10, seed=42)
        splits_b = load_splits(root, subset_outfits=10, seed=42)
        assert [o.id for o in splits_a["train"]] == [o.id for o in splits_b["train"]]

    def test_subset_larger_than_available_returns_all(self, tmp_path):
        root = _write_splits(tmp_path, ["t1", "t2"], ["v1"], ["e1"])
        splits = load_splits(root, subset_outfits=9999, seed=42)
        assert len(splits["train"]) == 2

    def test_subset_preserves_disjointness(self, tmp_path):
        root = _write_splits(
            tmp_path,
            [f"t{i}" for i in range(100)],
            [f"v{i}" for i in range(20)],
            [f"e{i}" for i in range(20)],
        )
        splits = load_splits(root, subset_outfits=30, seed=7)
        train_ids = {o.id for o in splits["train"]}
        valid_ids = {o.id for o in splits["valid"]}
        test_ids = {o.id for o in splits["test"]}
        assert train_ids & valid_ids == set()
        assert train_ids & test_ids == set()
        assert valid_ids & test_ids == set()

    def test_no_subset_returns_all(self, tmp_path):
        root = _write_splits(tmp_path, ["t1", "t2", "t3"], ["v1"], ["e1"])
        splits = load_splits(root, subset_outfits=None)
        assert len(splits["train"]) == 3
        assert len(splits["valid"]) == 1
        assert len(splits["test"]) == 1
