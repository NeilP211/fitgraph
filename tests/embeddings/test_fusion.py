"""Tests for fitgraph.embeddings.fusion."""

from __future__ import annotations

import numpy as np
import pytest

from fitgraph.embeddings.fusion import fuse


def _random_unit_rows(n: int, d: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, d)).astype(np.float32)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    return x


class TestFuse:
    def test_output_shape(self) -> None:
        img = _random_unit_rows(5, 512)
        txt = _random_unit_rows(5, 384)
        out = fuse(img, txt)
        assert out.shape == (5, 896), f"Expected (5, 896), got {out.shape}"

    def test_output_dtype(self) -> None:
        img = _random_unit_rows(5, 512)
        txt = _random_unit_rows(5, 384)
        out = fuse(img, txt)
        assert out.dtype == np.float32

    def test_rows_unit_norm(self) -> None:
        img = _random_unit_rows(10, 512)
        txt = _random_unit_rows(10, 384)
        out = fuse(img, txt)
        norms = np.linalg.norm(out, axis=1)
        np.testing.assert_allclose(norms, np.ones(len(norms)), atol=1e-5)

    def test_mismatched_rows_raises_value_error(self) -> None:
        img = _random_unit_rows(5, 512)
        txt = _random_unit_rows(4, 384)
        with pytest.raises(ValueError, match="Row count mismatch"):
            fuse(img, txt)

    def test_single_row(self) -> None:
        img = _random_unit_rows(1, 512)
        txt = _random_unit_rows(1, 384)
        out = fuse(img, txt)
        assert out.shape == (1, 896)
        np.testing.assert_allclose(np.linalg.norm(out, axis=1), [1.0], atol=1e-5)

    def test_finite_values(self) -> None:
        img = _random_unit_rows(8, 512)
        txt = _random_unit_rows(8, 384)
        out = fuse(img, txt)
        assert np.all(np.isfinite(out))
