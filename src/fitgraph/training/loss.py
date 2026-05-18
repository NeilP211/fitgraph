"""InfoNCE (contrastive) loss for outfit compatibility training."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch
import torch.nn.functional as F
from torch import Tensor

if TYPE_CHECKING:
    from fitgraph.models.type_aware import TypeAwareScorer


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


def type_aware_info_nce(
    anchor_emb: Tensor,
    positive_emb: Tensor,
    negative_emb: Tensor,
    candidate_space_ids: Tensor,
    scorer: TypeAwareScorer,
    temperature: float = 0.1,
) -> Tensor:
    """InfoNCE loss whose logits are computed in type-pair-specific subspaces.

    For each anchor, the candidate pool is ``[positives ; negatives]`` shared
    across the whole batch.  The compatibility logit of an anchor against a
    candidate is the :class:`~fitgraph.models.type_aware.TypeAwareScorer`
    similarity computed in the type-pair subspace of that anchor-candidate pair.
    The positive sits on the diagonal and is the cross-entropy target.

    Parameters
    ----------
    anchor_emb:
        Shared anchor embeddings, shape ``(B, D)``.
    positive_emb:
        Shared positive embeddings, shape ``(B, D)``; row i is the positive of
        anchor i.
    negative_emb:
        Shared (hard) negative embeddings, shape ``(M, D)``, shared across all
        anchors.
    candidate_space_ids:
        Long tensor ``(B, B + M)`` — the type-pair subspace id for each
        anchor against each candidate in ``[positives ; negatives]``.
    scorer:
        The :class:`TypeAwareScorer` used to compute type-aware similarities.
    temperature:
        Softmax temperature.

    Returns
    -------
    Tensor
        Scalar cross-entropy loss.
    """
    candidates = torch.cat([positive_emb, negative_emb], dim=0)  # (B+M, D)
    logits = scorer.score_matrix(anchor_emb, candidates, candidate_space_ids)
    logits = logits / temperature  # (B, B+M)
    targets = torch.arange(anchor_emb.size(0), device=anchor_emb.device)
    return F.cross_entropy(logits, targets)
