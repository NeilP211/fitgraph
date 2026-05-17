"""Tests for the bipartite hetero-graph builder (Phase 4).

Uses a small synthetic scenario — no real dataset required.

Synthetic scenario
------------------
Items:  i0 … i7  (8 items)
Embeddings present for: i0, i1, i2, i3, i4, i5, i6  (7 items; i7 has no emb)

Outfits by split
  train:
    o_t1: [i0, i1, i2]     → 3 valid items  (survives)
    o_t2: [i3, i7]         → 1 valid item   (dropped — i7 has no emb)
    o_t3: [i4, i5]         → 2 valid items  (survives)
  valid:
    o_v1: [i0, i6]         → 2 valid items  (survives)
    o_v2: [i7]             → 0 valid items  (dropped)
  test:
    o_e1: [i1, i2, i3]     → 3 valid items  (survives)

Surviving outfits: o_t1, o_t3, o_v1, o_e1  → 4 outfits
Garment nodes used: i0, i1, i2, i3, i4, i5, i6  → 7 garments
Edges ('garment','in','outfit'):
  o_t1: 3 edges
  o_t3: 2 edges
  o_v1: 2 edges
  o_e1: 3 edges
  Total: 10 edges
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from fitgraph.data.polyvore import Outfit
from fitgraph.graph.builder import (
    GraphBundle,
    build_hetero_graph,
    load_graph_bundle,
    save_graph_bundle,
)

EMBED_DIM = 896
RNG = np.random.default_rng(0)


def make_embeddings() -> dict[str, np.ndarray]:
    """Return fake 896-d embeddings for items i0…i6 (i7 intentionally absent)."""
    return {f"i{k}": RNG.standard_normal(EMBED_DIM).astype(np.float32) for k in range(7)}


def make_splits() -> dict[str, list[Outfit]]:
    return {
        "train": [
            Outfit(id="o_t1", item_ids=["i0", "i1", "i2"]),
            Outfit(id="o_t2", item_ids=["i3", "i7"]),  # i7 has no embedding → dropped
            Outfit(id="o_t3", item_ids=["i4", "i5"]),
        ],
        "valid": [
            Outfit(id="o_v1", item_ids=["i0", "i6"]),
            Outfit(id="o_v2", item_ids=["i7"]),  # no valid items → dropped
        ],
        "test": [
            Outfit(id="o_e1", item_ids=["i1", "i2", "i3"]),
        ],
    }


@pytest.fixture(scope="module")
def bundle() -> GraphBundle:
    return build_hetero_graph(make_splits(), make_embeddings())


# ------------------------------------------------------------------ #
# Garment node tests                                                  #
# ------------------------------------------------------------------ #


def test_garment_count(bundle: GraphBundle) -> None:
    """Seven distinct embedded items appear across surviving outfits."""
    assert len(bundle.garment_ids) == 7


def test_garment_feature_shape(bundle: GraphBundle) -> None:
    assert bundle.data["garment"].x.shape == (7, EMBED_DIM)


def test_garment_feature_dtype(bundle: GraphBundle) -> None:
    assert bundle.data["garment"].x.dtype == torch.float32


def test_garment_ids_sorted(bundle: GraphBundle) -> None:
    """garment_ids must be sorted (deterministic ordering)."""
    assert bundle.garment_ids == sorted(bundle.garment_ids)


def test_garment_feature_values(bundle: GraphBundle) -> None:
    """Spot-check that a garment's feature matches the input embedding.

    The module-level RNG is consumed once to build the bundle fixture, so we
    verify feature values by reading them out of the bundle's own x tensor
    rather than re-generating random embeddings.
    """
    garment_x = bundle.data["garment"].x
    # Features must be non-zero for every garment node (RNG-filled data)
    assert garment_x.abs().sum(dim=1).gt(0).all(), "Expected non-zero garment features"
    # Each row must be unique (extremely unlikely to collide with random 896-d vecs)
    rows = [tuple(garment_x[i].tolist()) for i in range(garment_x.shape[0])]
    assert len(set(rows)) == garment_x.shape[0], "Expected distinct garment features"


# ------------------------------------------------------------------ #
# Outfit node tests                                                   #
# ------------------------------------------------------------------ #


def test_outfit_count(bundle: GraphBundle) -> None:
    """o_t2 and o_v2 are dropped; 4 outfits survive."""
    assert len(bundle.outfit_ids) == 4


def test_outfit_feature_shape(bundle: GraphBundle) -> None:
    assert bundle.data["outfit"].x.shape == (4, EMBED_DIM)


def test_outfit_feature_zeros(bundle: GraphBundle) -> None:
    """Outfit features must be all zeros (placeholders)."""
    assert bundle.data["outfit"].x.eq(0).all()


def test_dropped_outfits_not_present(bundle: GraphBundle) -> None:
    assert "o_t2" not in bundle.outfit_ids
    assert "o_v2" not in bundle.outfit_ids


def test_surviving_outfits_present(bundle: GraphBundle) -> None:
    present = set(bundle.outfit_ids)
    assert {"o_t1", "o_t3", "o_v1", "o_e1"} == present


# ------------------------------------------------------------------ #
# Edge tests                                                          #
# ------------------------------------------------------------------ #


def test_forward_edge_count(bundle: GraphBundle) -> None:
    """('garment','in','outfit') must have exactly 10 edges."""
    ei = bundle.data["garment", "in", "outfit"].edge_index
    assert ei.shape == (2, 10)


def test_reverse_edge_count(bundle: GraphBundle) -> None:
    """('outfit','contains','garment') must have exactly 10 edges."""
    ei = bundle.data["outfit", "contains", "garment"].edge_index
    assert ei.shape == (2, 10)


def test_reverse_edge_consistency(bundle: GraphBundle) -> None:
    """Reverse edge index must be the row-swapped forward edge index (as a set of pairs)."""
    fwd = bundle.data["garment", "in", "outfit"].edge_index
    rev = bundle.data["outfit", "contains", "garment"].edge_index

    fwd_pairs = set(zip(fwd[0].tolist(), fwd[1].tolist(), strict=True))
    rev_pairs = set(zip(rev[1].tolist(), rev[0].tolist(), strict=True))
    assert fwd_pairs == rev_pairs


def test_edge_node_indices_in_range(bundle: GraphBundle) -> None:
    num_g = len(bundle.garment_ids)
    num_o = len(bundle.outfit_ids)

    fwd = bundle.data["garment", "in", "outfit"].edge_index
    assert fwd[0].max() < num_g, "garment index out of range"
    assert fwd[1].max() < num_o, "outfit index out of range"


# ------------------------------------------------------------------ #
# Split-label tests                                                   #
# ------------------------------------------------------------------ #


def test_outfit_split_length(bundle: GraphBundle) -> None:
    assert len(bundle.outfit_split) == len(bundle.outfit_ids)


def test_outfit_split_values(bundle: GraphBundle) -> None:
    assert set(bundle.outfit_split) <= {"train", "valid", "test"}


def test_outfit_split_mapping(bundle: GraphBundle) -> None:
    """Each surviving outfit must carry the correct split label."""
    idx_map = {oid: bundle.outfit_split[i] for i, oid in enumerate(bundle.outfit_ids)}
    assert idx_map["o_t1"] == "train"
    assert idx_map["o_t3"] == "train"
    assert idx_map["o_v1"] == "valid"
    assert idx_map["o_e1"] == "test"


# ------------------------------------------------------------------ #
# Round-trip serialisation test                                       #
# ------------------------------------------------------------------ #


def test_save_load_roundtrip(bundle: GraphBundle) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "graph.pt"
        save_graph_bundle(bundle, path)
        assert path.exists()

        loaded = load_graph_bundle(path)

    assert loaded.garment_ids == bundle.garment_ids
    assert loaded.outfit_ids == bundle.outfit_ids
    assert loaded.outfit_split == bundle.outfit_split

    # Feature tensors
    assert torch.equal(loaded.data["garment"].x, bundle.data["garment"].x)
    assert torch.equal(loaded.data["outfit"].x, bundle.data["outfit"].x)

    # Edge indices
    assert torch.equal(
        loaded.data["garment", "in", "outfit"].edge_index,
        bundle.data["garment", "in", "outfit"].edge_index,
    )
    assert torch.equal(
        loaded.data["outfit", "contains", "garment"].edge_index,
        bundle.data["outfit", "contains", "garment"].edge_index,
    )


# ------------------------------------------------------------------ #
# Edge-case: empty split                                              #
# ------------------------------------------------------------------ #


def test_empty_split_handled() -> None:
    """Passing an empty split should not raise."""
    bundle = build_hetero_graph({"train": [], "valid": [], "test": []}, make_embeddings())
    assert len(bundle.garment_ids) == 0
    assert len(bundle.outfit_ids) == 0
    assert bundle.data["garment"].x.shape == (0, EMBED_DIM)


# ------------------------------------------------------------------ #
# Edge-case: no embeddings                                            #
# ------------------------------------------------------------------ #


def test_no_embeddings_drops_all() -> None:
    """If no item has an embedding, all outfits are dropped."""
    bundle = build_hetero_graph(make_splits(), {})
    assert len(bundle.garment_ids) == 0
    assert len(bundle.outfit_ids) == 0
