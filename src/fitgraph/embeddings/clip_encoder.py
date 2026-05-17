"""CLIP image encoder wrapping open_clip ViT-B-32."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import open_clip
import torch
from PIL import Image, UnidentifiedImageError

from fitgraph.config import resolve_device


class ClipEncoder:
    """Encode images to L2-normalised 512-dim CLIP embeddings.

    Uses ``ViT-B-32`` with ``laion2b_s34b_b79k`` pretrained weights.
    """

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    def __init__(self, device: str | None = None) -> None:
        self.device = device or resolve_device()
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            self.MODEL_NAME,
            pretrained=self.PRETRAINED,
            device=self.device,
        )
        self._model.eval()

    def encode_images(self, paths: list[Path], batch_size: int = 64) -> np.ndarray:
        """Encode a list of image paths to L2-normalised CLIP embeddings.

        Parameters
        ----------
        paths:
            Paths to JPEG/PNG images. All paths must exist and be readable.
            If a file is corrupt or cannot be opened by PIL, a ``RuntimeError``
            is raised with the offending path in the message.
        batch_size:
            Number of images per forward pass.

        Returns
        -------
        np.ndarray of shape ``(N, 512)``, dtype float32, each row unit-norm.
        """
        if not paths:
            return np.empty((0, 512), dtype=np.float32)

        all_embeddings: list[np.ndarray] = []

        for start in range(0, len(paths), batch_size):
            batch_paths = paths[start : start + batch_size]
            tensors: list[torch.Tensor] = []
            for p in batch_paths:
                try:
                    img = Image.open(p).convert("RGB")
                except (OSError, UnidentifiedImageError) as exc:
                    raise RuntimeError(f"Failed to open image {p}: {exc}") from exc
                tensors.append(self._preprocess(img))

            batch = torch.stack(tensors).to(self.device)
            with torch.no_grad():
                features = self._model.encode_image(batch)
                features = features.float()
                # L2-normalise
                norms = features.norm(dim=1, keepdim=True).clamp(min=1e-12)
                features = features / norms

            all_embeddings.append(features.cpu().numpy())

        return np.concatenate(all_embeddings, axis=0).astype(np.float32)
