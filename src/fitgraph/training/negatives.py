"""Hard-negative mining for contrastive training."""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


def mine_hard_negatives(
    anchor_clip: Tensor,
    pool_clip: Tensor,
    forbidden: list[set[int]],
    k: int,
) -> Tensor:
    """Mine the hardest negatives from a candidate pool using CLIP similarity.

    For each anchor, scores all pool items by cosine similarity, masks out any
    forbidden (co-worn) pool indices, and returns the indices of the top-k most
    similar allowed candidates.

    Parameters
    ----------
    anchor_clip:
        CLIP embeddings for anchors, shape ``(B, 512)``.
    pool_clip:
        CLIP embeddings for the candidate pool, shape ``(P, 512)``.
    forbidden:
        List of length B. ``forbidden[i]`` is the set of pool indices that are
        co-worn with anchor i and must NOT be selected as negatives.
    k:
        Number of hard negatives to mine per anchor.

    Returns
    -------
    Tensor
        Long tensor of shape ``(B, k)`` containing the selected pool indices.
    """
    # L2-normalise both sets of embeddings
    anchor_norm = F.normalize(anchor_clip, p=2, dim=-1)  # (B, 512)
    pool_norm = F.normalize(pool_clip, p=2, dim=-1)  # (P, 512)

    # Cosine similarity matrix: (B, P)
    sims = anchor_norm @ pool_norm.T  # type: ignore[operator]

    B = anchor_clip.size(0)
    P = pool_clip.size(0)
    device = anchor_clip.device

    results: list[Tensor] = []
    for i in range(B):
        sim_i = sims[i].clone()  # (P,)

        # Mask out forbidden indices by setting their similarity to -inf
        if forbidden[i]:
            forbidden_idx = torch.tensor(
                list(forbidden[i]), dtype=torch.long, device=device
            )
            # Clamp to valid range in case indices exceed pool size
            forbidden_idx = forbidden_idx[forbidden_idx < P]
            if forbidden_idx.numel() > 0:
                sim_i[forbidden_idx] = float("-inf")

        # Top-k (capped to available valid candidates)
        available = P - len([f for f in forbidden[i] if f < P])
        actual_k = min(k, max(1, available))
        top_k = torch.topk(sim_i, actual_k).indices  # (actual_k,)

        # Pad with the last index if we got fewer than k
        if actual_k < k:
            pad = top_k[-1].expand(k - actual_k)
            top_k = torch.cat([top_k, pad])

        results.append(top_k)

    return torch.stack(results, dim=0)  # (B, k)
