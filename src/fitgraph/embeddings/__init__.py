"""FitGraph embeddings — CLIP image encoder, text encoder, and feature fusion."""

from fitgraph.embeddings.clip_encoder import ClipEncoder
from fitgraph.embeddings.fusion import fuse
from fitgraph.embeddings.text_encoder import TextEncoder

__all__ = ["ClipEncoder", "TextEncoder", "fuse"]
