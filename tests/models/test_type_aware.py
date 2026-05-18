"""Tests for type-aware embedding subspaces — synthetic, fast, no real data."""

from __future__ import annotations

import pickle
import tempfile
from pathlib import Path

import torch
import torch.nn.functional as F

from fitgraph.models.type_aware import TypeAwareScorer, TypeSpaceIndex
from fitgraph.training.loss import type_aware_info_nce

# A small synthetic typespaces list (positions are subspace ids).
_FAKE_TYPESPACES: list[tuple[str, str]] = [
    ("tops", "bottoms"),
    ("tops", "shoes"),
    ("bottoms", "shoes"),
    ("bags", "shoes"),
]


# ---------------------------------------------------------------------------
# TypeSpaceIndex
# ---------------------------------------------------------------------------


def test_num_spaces_is_pairs_plus_one() -> None:
    idx = TypeSpaceIndex(_FAKE_TYPESPACES)
    assert idx.num_spaces == len(_FAKE_TYPESPACES) + 1


def test_space_of_is_symmetric() -> None:
    idx = TypeSpaceIndex(_FAKE_TYPESPACES)
    for a, b in _FAKE_TYPESPACES:
        assert idx.space_of(a, b) == idx.space_of(b, a)


def test_space_of_matches_list_index() -> None:
    idx = TypeSpaceIndex(_FAKE_TYPESPACES)
    assert idx.space_of("tops", "bottoms") == 0
    assert idx.space_of("bottoms", "tops") == 0
    assert idx.space_of("bags", "shoes") == 3


def test_unknown_pair_returns_fallback() -> None:
    idx = TypeSpaceIndex(_FAKE_TYPESPACES)
    fallback = idx.num_spaces - 1
    assert idx.space_of("hats", "scarves") == fallback
    assert idx.space_of("tops", "hats") == fallback  # one known, one unknown
    assert idx.fallback_id == fallback


def test_real_typespaces_has_67_spaces() -> None:
    """The real typespaces.p (66 pairs) yields 67 spaces."""
    real_path = Path(
        "data/raw/polyvore-outfit-dataset/polyvore_outfits/disjoint/typespaces.p"
    )
    if not real_path.exists():
        return  # skip silently if dataset not present
    idx = TypeSpaceIndex.from_file(real_path)
    assert idx.num_spaces == 67


def test_index_roundtrip_dict_and_pickle() -> None:
    idx = TypeSpaceIndex(_FAKE_TYPESPACES)
    # dict roundtrip
    restored = TypeSpaceIndex.from_dict(idx.to_dict())
    assert restored.num_spaces == idx.num_spaces
    assert restored.space_of("tops", "shoes") == idx.space_of("tops", "shoes")
    # pickle roundtrip
    unpickled = pickle.loads(pickle.dumps(idx))
    assert unpickled.num_spaces == idx.num_spaces
    assert unpickled.space_of("bags", "shoes") == idx.space_of("bags", "shoes")


def test_index_json_roundtrip() -> None:
    idx = TypeSpaceIndex(_FAKE_TYPESPACES)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "type_index.json"
        idx.save_json(path)
        restored = TypeSpaceIndex.load_json(path)
    assert restored.num_spaces == idx.num_spaces
    assert restored.space_of("tops", "bottoms") == 0


# ---------------------------------------------------------------------------
# TypeAwareScorer
# ---------------------------------------------------------------------------


def test_score_pairs_shape_and_range() -> None:
    torch.manual_seed(0)
    scorer = TypeAwareScorer(num_spaces=5, dim=16)
    b = 12
    ea = F.normalize(torch.randn(b, 16), dim=-1)
    eb = F.normalize(torch.randn(b, 16), dim=-1)
    space_ids = torch.randint(0, 5, (b,))
    out = scorer.score_pairs(ea, eb, space_ids)
    assert out.shape == (b,)
    assert torch.isfinite(out).all()
    assert (out >= -1.0001).all() and (out <= 1.0001).all()


def test_score_matrix_shape_and_range() -> None:
    torch.manual_seed(1)
    scorer = TypeAwareScorer(num_spaces=5, dim=16)
    b, c = 7, 9
    anchors = F.normalize(torch.randn(b, 16), dim=-1)
    cands = F.normalize(torch.randn(c, 16), dim=-1)
    space_ids = torch.randint(0, 5, (b, c))
    out = scorer.score_matrix(anchors, cands, space_ids)
    assert out.shape == (b, c)
    assert torch.isfinite(out).all()
    assert (out >= -1.0001).all() and (out <= 1.0001).all()


def test_init_masks_approximate_plain_cosine() -> None:
    """With masks at init (ones -> softplus = uniform scaling), type-aware
    similarity equals plain cosine similarity."""
    torch.manual_seed(2)
    scorer = TypeAwareScorer(num_spaces=4, dim=32)
    b = 10
    ea = F.normalize(torch.randn(b, 32), dim=-1)
    eb = F.normalize(torch.randn(b, 32), dim=-1)
    space_ids = torch.randint(0, 4, (b,))

    type_aware = scorer.score_pairs(ea, eb, space_ids)
    plain = F.cosine_similarity(ea, eb, dim=-1)
    assert torch.allclose(type_aware, plain, atol=1e-5)


def test_score_matrix_consistent_with_score_pairs() -> None:
    """The diagonal of score_matrix equals score_pairs for matched pairs."""
    torch.manual_seed(3)
    scorer = TypeAwareScorer(num_spaces=6, dim=24)
    # Perturb masks so spaces actually differ.
    with torch.no_grad():
        scorer.masks.add_(0.5 * torch.randn_like(scorer.masks))
    n = 8
    embs = F.normalize(torch.randn(n, 24), dim=-1)
    pair_space = torch.randint(0, 6, (n,))

    pairs = scorer.score_pairs(embs, embs, pair_space)

    space_mat = pair_space.unsqueeze(1).expand(n, n)
    matrix = scorer.score_matrix(embs, embs, space_mat)
    diag = matrix.diagonal()
    assert torch.allclose(pairs, diag, atol=1e-5)


def test_scorer_gradients_flow() -> None:
    """Gradients reach the mask parameter through score_matrix."""
    torch.manual_seed(4)
    scorer = TypeAwareScorer(num_spaces=4, dim=16)
    anchors = F.normalize(torch.randn(5, 16), dim=-1)
    cands = F.normalize(torch.randn(6, 16), dim=-1)
    space_ids = torch.randint(0, 4, (5, 6))
    out = scorer.score_matrix(anchors, cands, space_ids)
    out.sum().backward()
    assert scorer.masks.grad is not None
    assert scorer.masks.grad.abs().sum() > 0


# ---------------------------------------------------------------------------
# Realistic-scale regression test — guards against the (B*C*dim) memory blowup
# ---------------------------------------------------------------------------


def test_score_matrix_large_scale_no_memory_blowup() -> None:
    """score_matrix with B=1024, C=1500, dim=256 completes with correct shape.

    Before the chunked fix, this would materialise a 1024 * 1500 * 256 * 4
    ≈ 1.6 GB intermediate tensor per call (and much more in a real batch),
    causing OOM on memory-limited machines.  The chunked implementation keeps
    peak memory at anchor_chunk * C * dim * 4 ≈ 390 MB.
    """
    torch.manual_seed(99)
    B, C, D = 1024, 1500, 256
    num_spaces = 67  # realistic polyvore typespace count

    scorer = TypeAwareScorer(num_spaces=num_spaces, dim=D)
    anchors = F.normalize(torch.randn(B, D), dim=-1)
    candidates = F.normalize(torch.randn(C, D), dim=-1)
    space_ids = torch.randint(0, num_spaces, (B, C))

    out = scorer.score_matrix(anchors, candidates, space_ids)

    assert out.shape == (B, C), f"Expected ({B}, {C}), got {out.shape}"
    assert torch.isfinite(out).all(), "Output contains non-finite values"
    assert (out >= -1.0001).all() and (out <= 1.0001).all(), (
        "Cosine similarities out of [-1, 1]"
    )

    # Also exercise type_aware_info_nce at scale: B anchors, B positives, M=476
    # negatives so that the negative pool is bounded (peak B*M*dim not B*C*dim).
    M = C - B  # 476
    negative_emb = F.normalize(torch.randn(M, D), dim=-1)
    # New signature: separate pos_space_ids (B,) and neg_space_ids (B, M).
    pos_space_ids = torch.randint(0, num_spaces, (B,))
    neg_space_ids = torch.randint(0, num_spaces, (B, M))
    loss = type_aware_info_nce(
        anchors,
        candidates[:B],       # first B candidates as positives
        negative_emb,
        pos_space_ids,
        neg_space_ids,
        scorer,
        temperature=0.1,
    )
    assert loss.ndim == 0, "type_aware_info_nce should return a scalar"
    assert torch.isfinite(loss), "type_aware_info_nce loss is not finite"


def test_score_matrix_chunked_matches_unchunked() -> None:
    """Chunked result is numerically identical to a single-chunk (unchunked) call."""
    torch.manual_seed(42)
    B, C, D = 64, 80, 32
    num_spaces = 5

    scorer = TypeAwareScorer(num_spaces=num_spaces, dim=D)
    with torch.no_grad():
        scorer.masks.add_(0.3 * torch.randn_like(scorer.masks))

    anchors = F.normalize(torch.randn(B, D), dim=-1)
    candidates = F.normalize(torch.randn(C, D), dim=-1)
    space_ids = torch.randint(0, num_spaces, (B, C))

    # anchor_chunk > B => single chunk, effectively the old code-path
    out_single = scorer.score_matrix(anchors, candidates, space_ids, anchor_chunk=B + 1)
    # anchor_chunk much smaller => multiple chunks
    out_multi = scorer.score_matrix(anchors, candidates, space_ids, anchor_chunk=16)

    assert torch.allclose(out_single, out_multi, atol=1e-5), (
        "Chunked and unchunked score_matrix results differ"
    )
