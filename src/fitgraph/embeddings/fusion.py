"""Feature fusion: concatenate CLIP and text embeddings then L2-normalise."""

from __future__ import annotations

import numpy as np


def fuse(image_emb: np.ndarray, text_emb: np.ndarray) -> np.ndarray:
    """Concatenate image and text embeddings and L2-normalise each row.

    Parameters
    ----------
    image_emb:
        Array of shape ``(N, D_img)`` — e.g. ``(N, 512)`` CLIP embeddings.
    text_emb:
        Array of shape ``(N, D_txt)`` — e.g. ``(N, 384)`` text embeddings.

    Returns
    -------
    np.ndarray of shape ``(N, D_img + D_txt)`` (e.g. ``(N, 896)``), dtype
    float32, each row unit-norm.

    Raises
    ------
    ValueError
        If ``image_emb`` and ``text_emb`` have different numbers of rows.
    """
    if image_emb.shape[0] != text_emb.shape[0]:
        raise ValueError(
            f"Row count mismatch: image_emb has {image_emb.shape[0]} rows "
            f"but text_emb has {text_emb.shape[0]} rows."
        )

    concatenated = np.concatenate([image_emb, text_emb], axis=1).astype(np.float32)
    norms = np.linalg.norm(concatenated, axis=1, keepdims=True).clip(min=1e-12)
    return (concatenated / norms).astype(np.float32)
