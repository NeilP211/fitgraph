"""InfoNCE (contrastive) loss for outfit compatibility training."""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


def info_nce(
    anchor: Tensor,
    positive: Tensor,
    extra_negatives: Tensor | None = None,
    temperature: float = 0.1,
) -> Tensor:
    """Compute InfoNCE loss with in-batch negatives and optional hard negatives.

    For anchor i, the positives of all j != i serve as in-batch negatives
    (standard NT-Xent / SimCLR approach). Optionally, ``extra_negatives``
    (e.g. hard-mined candidates) are appended to the candidate pool and shared
    across the whole batch.

    Parameters
    ----------
    anchor:
        L2-normalised anchor embeddings, shape ``(B, D)``.
    positive:
        L2-normalised positive embeddings, shape ``(B, D)``. Row i is the
        positive counterpart of anchor i.
    extra_negatives:
        Optional additional negative embeddings of shape ``(M, D)``, shared
        across all anchors.
    temperature:
        Softmax temperature (lower = sharper contrast).

    Returns
    -------
    Tensor
        Scalar cross-entropy loss.
    """
    # candidates = [positive ; extra_negatives]  shape (B + M, D) or (B, D)
    if extra_negatives is not None:
        candidates = torch.cat([positive, extra_negatives], dim=0)  # (B+M, D)
    else:
        candidates = positive  # (B, D)

    # logits: (B, B+M) or (B, B)
    logits = anchor @ candidates.T / temperature  # type: ignore[operator]

    # Target for anchor i is the i-th candidate (its own positive)
    targets = torch.arange(anchor.size(0), device=anchor.device)

    return F.cross_entropy(logits, targets)
