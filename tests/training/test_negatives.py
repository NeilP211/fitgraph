"""Tests for hard-negative mining."""

from __future__ import annotations

import torch
import torch.nn.functional as F

from fitgraph.training.negatives import mine_hard_negatives


def _norm(x: torch.Tensor) -> torch.Tensor:
    return F.normalize(x, p=2, dim=-1)


def test_no_forbidden_returns_most_similar() -> None:
    """Without forbidden indices, returns the most CLIP-similar pool items."""
    torch.manual_seed(0)
    B, P, D, k = 4, 20, 512, 3
    anchor_clip = _norm(torch.randn(B, D))
    pool_clip = _norm(torch.randn(P, D))

    # Compute expected top-k manually
    sims = anchor_clip @ pool_clip.T  # (B, P)
    expected = sims.topk(k, dim=-1).indices  # (B, k)

    forbidden: list[set[int]] = [set() for _ in range(B)]
    result = mine_hard_negatives(anchor_clip, pool_clip, forbidden, k)

    assert result.shape == (B, k), f"Expected ({B}, {k}), got {result.shape}"
    # Check that returned indices are the same as expected top-k
    for i in range(B):
        res_set = set(result[i].tolist())
        exp_set = set(expected[i].tolist())
        assert res_set == exp_set, (
            f"Anchor {i}: expected {exp_set}, got {res_set}"
        )


def test_forbidden_indices_excluded() -> None:
    """Mined negatives never include forbidden indices."""
    torch.manual_seed(1)
    B, P, D, k = 6, 30, 512, 5
    anchor_clip = _norm(torch.randn(B, D))
    pool_clip = _norm(torch.randn(P, D))

    # Mark a significant fraction of pool as forbidden for each anchor
    forbidden: list[set[int]] = []
    for i in range(B):
        # Forbid indices 0..9 for even anchors, 10..19 for odd
        if i % 2 == 0:
            forbidden.append(set(range(10)))
        else:
            forbidden.append(set(range(10, 20)))

    result = mine_hard_negatives(anchor_clip, pool_clip, forbidden, k)

    assert result.shape == (B, k), f"Expected ({B}, {k}), got {result.shape}"
    for i in range(B):
        chosen = set(result[i].tolist())
        for idx in chosen:
            assert idx not in forbidden[i], (
                f"Anchor {i}: forbidden index {idx} was selected. "
                f"Forbidden={forbidden[i]}, chosen={chosen}"
            )


def test_result_shape_and_dtype() -> None:
    """Output is a long tensor of correct shape."""
    torch.manual_seed(2)
    B, P, D, k = 3, 10, 512, 4
    anchor_clip = _norm(torch.randn(B, D))
    pool_clip = _norm(torch.randn(P, D))
    forbidden: list[set[int]] = [set() for _ in range(B)]

    result = mine_hard_negatives(anchor_clip, pool_clip, forbidden, k)

    assert result.shape == (B, k)
    assert result.dtype == torch.long


def test_most_similar_chosen_when_not_forbidden() -> None:
    """The single most similar pool item (not forbidden) is always in result."""
    torch.manual_seed(3)
    B, P, D, k = 2, 15, 512, 3
    anchor_clip = _norm(torch.randn(B, D))
    pool_clip = _norm(torch.randn(P, D))

    sims = anchor_clip @ pool_clip.T  # (B, P)
    forbidden: list[set[int]] = [set() for _ in range(B)]

    result = mine_hard_negatives(anchor_clip, pool_clip, forbidden, k)

    for i in range(B):
        best_idx = int(sims[i].argmax())
        assert best_idx in result[i].tolist(), (
            f"Anchor {i}: most similar index {best_idx} not in result {result[i].tolist()}"
        )


def test_forbidden_is_most_similar_selects_next_best() -> None:
    """When the most similar item is forbidden, the next best is selected."""
    torch.manual_seed(4)
    P, D, k = 20, 512, 1
    anchor_clip = _norm(torch.randn(1, D))
    pool_clip = _norm(torch.randn(P, D))

    sims = anchor_clip @ pool_clip.T  # (1, P)
    top2 = sims[0].topk(2).indices.tolist()
    best, second = top2[0], top2[1]

    # Forbid the most similar item
    forbidden: list[set[int]] = [{best}]

    result = mine_hard_negatives(anchor_clip, pool_clip, forbidden, k)

    assert result[0, 0].item() == second, (
        f"Expected second-best {second} but got {result[0, 0].item()}"
    )
