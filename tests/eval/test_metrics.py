"""Tests for fitgraph.eval.metrics — pure, fast, synthetic data only."""

from __future__ import annotations

import random

import pytest

from fitgraph.eval.metrics import accuracy, recall_at_k, roc_auc


class TestRocAuc:
    def test_perfect_ordering_gives_1(self) -> None:
        """Perfect ranking: scores perfectly match labels."""
        labels = [1, 1, 1, 0, 0, 0]
        scores = [0.9, 0.8, 0.7, 0.3, 0.2, 0.1]
        assert roc_auc(scores, labels) == pytest.approx(1.0)

    def test_reversed_ordering_gives_0(self) -> None:
        """Worst-case ranking: scores are anti-correlated with labels."""
        labels = [1, 1, 1, 0, 0, 0]
        scores = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
        assert roc_auc(scores, labels) == pytest.approx(0.0)

    def test_random_scores_near_half(self) -> None:
        """Randomly shuffled scores should produce AUC close to 0.5."""
        rng = random.Random(0)
        n = 200
        labels = [1] * (n // 2) + [0] * (n // 2)
        scores = [rng.random() for _ in range(n)]
        auc = roc_auc(scores, labels)
        assert 0.3 <= auc <= 0.7

    def test_binary_perfect_separation(self) -> None:
        labels = [0, 1, 0, 1]
        scores = [0.1, 0.9, 0.2, 0.8]
        assert roc_auc(scores, labels) == pytest.approx(1.0)


class TestAccuracy:
    def test_all_correct(self) -> None:
        preds = [1, 2, 3]
        targets = [1, 2, 3]
        assert accuracy(preds, targets) == pytest.approx(1.0)

    def test_all_wrong(self) -> None:
        preds = [0, 0, 0]
        targets = [1, 2, 3]
        assert accuracy(preds, targets) == pytest.approx(0.0)

    def test_partial(self) -> None:
        preds = [1, 0, 3, 0]
        targets = [1, 2, 3, 4]
        assert accuracy(preds, targets) == pytest.approx(0.5)

    def test_empty(self) -> None:
        assert accuracy([], []) == pytest.approx(0.0)

    def test_strings(self) -> None:
        preds = ["a", "b", "c"]
        targets = ["a", "x", "c"]
        assert accuracy(preds, targets) == pytest.approx(2 / 3)


class TestRecallAtK:
    def test_relevant_in_top_k(self) -> None:
        ranked = [["a", "b", "c", "d", "e"]]
        relevant = ["c"]
        assert recall_at_k(ranked, relevant, k=3) == pytest.approx(1.0)

    def test_relevant_outside_top_k(self) -> None:
        ranked = [["a", "b", "c", "d", "e"]]
        relevant = ["e"]
        assert recall_at_k(ranked, relevant, k=3) == pytest.approx(0.0)

    def test_mixed_queries(self) -> None:
        ranked = [
            ["x", "y", "z"],  # relevant=y → in top-2
            ["a", "b", "c"],  # relevant=c → NOT in top-2
            ["p", "q", "r"],  # relevant=p → in top-2
        ]
        relevant = ["y", "c", "p"]
        assert recall_at_k(ranked, relevant, k=2) == pytest.approx(2 / 3)

    def test_k_equals_1_exact_match(self) -> None:
        ranked = [["best", "second", "third"]]
        relevant = ["best"]
        assert recall_at_k(ranked, relevant, k=1) == pytest.approx(1.0)

    def test_k_equals_1_no_match(self) -> None:
        ranked = [["best", "second", "third"]]
        relevant = ["second"]
        assert recall_at_k(ranked, relevant, k=1) == pytest.approx(0.0)

    def test_empty_queries(self) -> None:
        assert recall_at_k([], [], k=10) == pytest.approx(0.0)

    def test_k_larger_than_list(self) -> None:
        ranked = [["a", "b"]]
        relevant = ["b"]
        assert recall_at_k(ranked, relevant, k=100) == pytest.approx(1.0)
