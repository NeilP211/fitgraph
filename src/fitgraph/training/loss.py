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
    negative_pool_emb: Tensor,
    pos_space_ids: Tensor,
    neg_space_ids: Tensor,
    scorer: TypeAwareScorer,
    temperature: float = 0.1,
) -> Tensor:
    """InfoNCE loss with a BOUNDED shared negative pool (memory-efficient form).

    Peak compute is ``B * M * dim`` (not ``B * B * dim``), where M is the size
    of the shared negative pool.  With B=1024, M=256, dim=256 the intermediate
    tensor is ``1024 * 256 * 256 * 4 bytes ≈ 268 MB``, well within MPS limits.

    For each anchor i the logit layout is::

        [pos_score_i  |  neg_score_i_0, ..., neg_score_i_{M-1}]   shape (1+M,)

    The cross-entropy target is index 0 (the positive) for every anchor.

    Parameters
    ----------
    anchor_emb:
        Anchor embeddings, shape ``(B, D)``.
    positive_emb:
        Positive embeddings, shape ``(B, D)``; row i is the positive of anchor i.
    negative_pool_emb:
        Shared negative-pool embeddings, shape ``(M, D)``.  The same M items
        are used as negatives for every anchor.
    pos_space_ids:
        Long tensor ``(B,)`` — type-pair subspace id for each anchor-positive
        pair.  Passed to :meth:`~fitgraph.models.type_aware.TypeAwareScorer.score_pairs`.
    neg_space_ids:
        Long tensor ``(B, M)`` — type-pair subspace id for each
        anchor-negative pair.  Passed to
        :meth:`~fitgraph.models.type_aware.TypeAwareScorer.score_matrix`.
    scorer:
        The :class:`~fitgraph.models.type_aware.TypeAwareScorer` used to compute
        type-aware similarities.
    temperature:
        Softmax temperature.

    Returns
    -------
    Tensor
        Scalar cross-entropy loss.
    """
    # Positive scores: one per anchor, shape (B,)
    pos_scores = scorer.score_pairs(anchor_emb, positive_emb, pos_space_ids)

    # Negative scores: (B, M) via score_matrix with bounded M
    neg_scores = scorer.score_matrix(anchor_emb, negative_pool_emb, neg_space_ids)

    # Logits: positives in column 0, then negatives.  Shape (B, 1+M).
    logits = torch.cat([pos_scores.unsqueeze(1), neg_scores], dim=1) / temperature

    # Target is always index 0 (the positive column).
    targets = torch.zeros(anchor_emb.size(0), dtype=torch.long, device=anchor_emb.device)
    return F.cross_entropy(logits, targets)
