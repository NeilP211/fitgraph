"""Text encoder wrapping sentence-transformers all-MiniLM-L6-v2."""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from fitgraph.config import resolve_device


class TextEncoder:
    """Encode text to L2-normalised 384-dim sentence embeddings.

    Uses ``all-MiniLM-L6-v2`` from the ``sentence-transformers`` library.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, device: str | None = None) -> None:
        self.device = device or resolve_device()
        self._model = SentenceTransformer(self.MODEL_NAME, device=self.device)

    def encode(self, texts: list[str], batch_size: int = 128) -> np.ndarray:
        """Encode a list of strings to L2-normalised sentence embeddings.

        Parameters
        ----------
        texts:
            Input strings to encode.
        batch_size:
            Number of sentences per forward pass.

        Returns
        -------
        np.ndarray of shape ``(N, 384)``, dtype float32, each row unit-norm.
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        embeddings: np.ndarray = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings.astype(np.float32)
