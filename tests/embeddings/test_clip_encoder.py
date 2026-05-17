"""Tests for fitgraph.embeddings.clip_encoder."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from fitgraph.embeddings.clip_encoder import ClipEncoder


def _make_jpeg(path: Path, width: int = 64, height: int = 64) -> Path:
    """Write a small solid-colour JPEG to *path* and return *path*."""
    img = Image.new("RGB", (width, height), color=(120, 80, 200))
    img.save(path, format="JPEG")
    return path


@pytest.fixture(scope="module")
def encoder() -> ClipEncoder:
    return ClipEncoder()


@pytest.fixture()
def two_images(tmp_path: Path) -> list[Path]:
    return [
        _make_jpeg(tmp_path / "a.jpg"),
        _make_jpeg(tmp_path / "b.jpg", width=32, height=32),
    ]


class TestClipEncoder:
    def test_output_shape(self, encoder: ClipEncoder, two_images: list[Path]) -> None:
        emb = encoder.encode_images(two_images)
        assert emb.shape == (2, 512), f"Expected (2, 512), got {emb.shape}"

    def test_output_dtype(self, encoder: ClipEncoder, two_images: list[Path]) -> None:
        emb = encoder.encode_images(two_images)
        assert emb.dtype == np.float32

    def test_finite_values(self, encoder: ClipEncoder, two_images: list[Path]) -> None:
        emb = encoder.encode_images(two_images)
        assert np.all(np.isfinite(emb)), "Embeddings contain non-finite values"

    def test_unit_norm(self, encoder: ClipEncoder, two_images: list[Path]) -> None:
        emb = encoder.encode_images(two_images)
        norms = np.linalg.norm(emb, axis=1)
        np.testing.assert_allclose(norms, np.ones(len(norms)), atol=1e-5)

    def test_empty_input(self, encoder: ClipEncoder) -> None:
        emb = encoder.encode_images([])
        assert emb.shape == (0, 512)

    def test_corrupt_file_raises_runtime_error(self, encoder: ClipEncoder, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.jpg"
        corrupt.write_bytes(b"not an image")
        with pytest.raises(RuntimeError, match="Failed to open image"):
            encoder.encode_images([corrupt])
