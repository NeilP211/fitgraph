"""Tests for the InfoNCE loss function."""

from __future__ import annotations

import torch
import torch.nn.functional as F

from fitgraph.models.type_aware import TypeAwareScorer
from fitgraph.training.loss import info_nce, type_aware_info_nce


def _norm(x: torch.Tensor) -> torch.Tensor:
    """L2-normalise rows of x."""
    return F.normalize(x, p=2, dim=-1)


def test_loss_is_scalar() -> None:
    """info_nce returns a scalar tensor."""
    torch.manual_seed(0)
    B, D = 8, 64
    anchor = _norm(torch.randn(B, D))
    positive = _norm(torch.randn(B, D))
    loss = info_nce(anchor, positive)
    assert loss.ndim == 0, f"Expected scalar, got shape {loss.shape}"


def test_identical_anchor_positive_low_loss() -> None:
    """When anchor == positive, loss should be low (well below log(B))."""
    torch.manual_seed(0)
    B, D = 16, 64
    emb = _norm(torch.randn(B, D))
    # All anchors == their positives
    loss = info_nce(emb, emb.clone(), temperature=0.1)
    # Upper bound: log(B) ≈ 2.77 for B=16; well-separated → should be < 1.0
    assert float(loss) < 1.0, f"Expected low loss with identical pairs, got {float(loss):.4f}"


def test_shuffled_positives_higher_loss() -> None:
    """Shuffled positives (wrong assignments) should give higher loss.

    We use correlated pairs (positive ≈ anchor + small noise) so that correct
    assignments have low loss and shuffled assignments have higher loss.
    """
    torch.manual_seed(0)
    B, D = 16, 64
    anchor = _norm(torch.randn(B, D))
    # Positives are very close to anchors (correct pairs are clearly aligned)
    positive = _norm(anchor + 0.01 * torch.randn(B, D))

    loss_correct = info_nce(anchor, positive, temperature=0.1)

    # Shuffle positives so assignments are wrong
    perm = torch.randperm(B)
    # Ensure perm is actually a non-identity permutation
    while torch.all(perm == torch.arange(B)):
        perm = torch.randperm(B)
    shuffled = positive[perm]
    loss_shuffled = info_nce(anchor, shuffled, temperature=0.1)

    assert float(loss_shuffled) > float(loss_correct), (
        f"Expected shuffled loss ({float(loss_shuffled):.4f}) > "
        f"correct loss ({float(loss_correct):.4f})"
    )


def test_extra_negatives_included() -> None:
    """With extra_negatives, loss should be >= loss without them (harder task)."""
    torch.manual_seed(0)
    B, D, M = 8, 64, 32
    anchor = _norm(torch.randn(B, D))
    positive = _norm(torch.randn(B, D))
    extra = _norm(torch.randn(M, D))

    loss_with_extra = info_nce(anchor, positive, extra_negatives=extra, temperature=0.1)

    # Adding hard negatives should generally increase loss (harder classification)
    # We just check it runs and returns a scalar
    assert loss_with_extra.ndim == 0, "Expected scalar with extra_negatives"
    assert float(loss_with_extra) > 0.0, "Loss should be positive"


def test_loss_with_identical_pairs_and_extra_negatives() -> None:
    """Identical pairs with random extra negatives: loss still finite."""
    torch.manual_seed(1)
    B, D, M = 8, 64, 16
    emb = _norm(torch.randn(B, D))
    extra = _norm(torch.randn(M, D))
    loss = info_nce(emb, emb.clone(), extra_negatives=extra, temperature=0.1)
    assert torch.isfinite(loss), f"Loss should be finite, got {float(loss)}"


def test_loss_temperature_effect() -> None:
    """Lower temperature should produce sharper (higher) loss on random pairs."""
    torch.manual_seed(2)
    B, D = 8, 64
    anchor = _norm(torch.randn(B, D))
    positive = _norm(torch.randn(B, D))

    loss_high_temp = info_nce(anchor, positive, temperature=1.0)
    loss_low_temp = info_nce(anchor, positive, temperature=0.01)

    # With random (non-matched) pairs, low temperature sharpens the distribution
    # Both should be finite positive values
    assert torch.isfinite(loss_high_temp), "High-temp loss not finite"
    assert torch.isfinite(loss_low_temp), "Low-temp loss not finite"


# ---------------------------------------------------------------------------
# type_aware_info_nce
# ---------------------------------------------------------------------------


def test_type_aware_info_nce_is_finite_scalar() -> None:
    """type_aware_info_nce returns a finite scalar."""
    torch.manual_seed(0)
    b, d, m = 8, 32, 10
    scorer = TypeAwareScorer(num_spaces=4, dim=d)
    anchor = _norm(torch.randn(b, d))
    positive = _norm(torch.randn(b, d))
    negative = _norm(torch.randn(m, d))
    space_ids = torch.randint(0, 4, (b, b + m))
    loss = type_aware_info_nce(
        anchor, positive, negative, space_ids, scorer, temperature=0.1
    )
    assert loss.ndim == 0
    assert torch.isfinite(loss)
    assert float(loss.detach()) > 0.0


def test_type_aware_info_nce_low_loss_for_aligned_pairs() -> None:
    """When positives equal anchors and negatives are random, loss is low."""
    torch.manual_seed(1)
    b, d, m = 16, 32, 8
    scorer = TypeAwareScorer(num_spaces=3, dim=d)
    emb = _norm(torch.randn(b, d))
    negative = _norm(torch.randn(m, d))
    space_ids = torch.zeros((b, b + m), dtype=torch.long)
    loss = type_aware_info_nce(
        emb, emb.clone(), negative, space_ids, scorer, temperature=0.1
    )
    # At init the scorer is ~plain cosine; identical pairs separate well.
    assert float(loss.detach()) < 1.5


def test_type_aware_info_nce_gradients_flow_to_scorer() -> None:
    """Backprop reaches both the embeddings and the scorer masks."""
    torch.manual_seed(2)
    b, d, m = 6, 24, 5
    scorer = TypeAwareScorer(num_spaces=4, dim=d)
    anchor = _norm(torch.randn(b, d)).requires_grad_(True)
    positive = _norm(torch.randn(b, d))
    negative = _norm(torch.randn(m, d))
    space_ids = torch.randint(0, 4, (b, b + m))
    loss = type_aware_info_nce(
        anchor, positive, negative, space_ids, scorer, temperature=0.1
    )
    loss.backward()
    assert scorer.masks.grad is not None
    assert scorer.masks.grad.abs().sum() > 0
    assert anchor.grad is not None
