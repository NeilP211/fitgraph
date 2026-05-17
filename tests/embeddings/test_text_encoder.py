"""Tests for fitgraph.embeddings.text_encoder."""

from __future__ import annotations

import numpy as np
import pytest

from fitgraph.embeddings.text_encoder import TextEncoder


@pytest.fixture(scope="module")
def encoder() -> TextEncoder:
    return TextEncoder()


@pytest.fixture()
def two_texts() -> list[str]:
    return [
        "Blue denim jacket. A classic slim-fit denim jacket in indigo wash.",
        "White sneakers. Clean low-top leather sneakers with rubber sole.",
    ]


class TestTextEncoder:
    def test_output_shape(self, encoder: TextEncoder, two_texts: list[str]) -> None:
        emb = encoder.encode(two_texts)
        assert emb.shape == (2, 384), f"Expected (2, 384), got {emb.shape}"

    def test_output_dtype(self, encoder: TextEncoder, two_texts: list[str]) -> None:
        emb = encoder.encode(two_texts)
        assert emb.dtype == np.float32

    def test_finite_values(self, encoder: TextEncoder, two_texts: list[str]) -> None:
        emb = encoder.encode(two_texts)
        assert np.all(np.isfinite(emb)), "Embeddings contain non-finite values"

    def test_unit_norm(self, encoder: TextEncoder, two_texts: list[str]) -> None:
        emb = encoder.encode(two_texts)
        norms = np.linalg.norm(emb, axis=1)
        np.testing.assert_allclose(norms, np.ones(len(norms)), atol=1e-5)

    def test_empty_input(self, encoder: TextEncoder) -> None:
        emb = encoder.encode([])
        assert emb.shape == (0, 384)

    def test_single_string(self, encoder: TextEncoder) -> None:
        emb = encoder.encode(["A single garment."])
        assert emb.shape == (1, 384)
        norms = np.linalg.norm(emb, axis=1)
        np.testing.assert_allclose(norms, [1.0], atol=1e-5)
