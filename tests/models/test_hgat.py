"""Tests for the HGAT model."""

from __future__ import annotations

import pytest
import torch
import torch.nn.functional as F
from torch_geometric.data import HeteroData

from fitgraph.models.hgat import HGAT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_tiny_graph(
    num_garments: int = 6,
    num_outfits: int = 2,
    in_dim: int = 896,
) -> HeteroData:
    """Build a tiny HeteroData graph for testing."""
    torch.manual_seed(0)
    data = HeteroData()
    data["garment"].x = torch.randn(num_garments, in_dim)
    data["outfit"].x = torch.zeros(num_outfits, in_dim)

    # Garments 0,1,2 in outfit 0; garments 3,4,5 in outfit 1
    # Garment 5 has NO edges (isolated)
    src = [0, 1, 2, 3, 4]
    dst = [0, 0, 0, 1, 1]
    edge_g_o = torch.tensor([src, dst], dtype=torch.long)
    edge_o_g = torch.tensor([dst, src], dtype=torch.long)

    data["garment", "in", "outfit"].edge_index = edge_g_o
    data["outfit", "contains", "garment"].edge_index = edge_o_g

    return data


@pytest.fixture()
def tiny_model() -> HGAT:
    return HGAT(in_dim=896, hidden_dim=32, num_layers=2, num_heads=4, dropout=0.0)


@pytest.fixture()
def tiny_data() -> HeteroData:
    return make_tiny_graph()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_forward_shape(tiny_model: HGAT, tiny_data: HeteroData) -> None:
    """forward() returns (num_garments, hidden_dim)."""
    out = tiny_model(tiny_data)
    assert out.shape == (6, 32), f"Expected (6, 32), got {out.shape}"


def test_forward_l2_normalized(tiny_model: HGAT, tiny_data: HeteroData) -> None:
    """Garment embeddings from forward() are L2-normalized (row norms ≈ 1)."""
    out = tiny_model(tiny_data)
    norms = out.norm(dim=-1)
    assert torch.allclose(norms, torch.ones(6), atol=1e-5), (
        f"Row norms not ≈ 1: {norms}"
    )


def test_forward_gradient_flows(tiny_model: HGAT, tiny_data: HeteroData) -> None:
    """Gradients flow through forward() and reach model parameters."""
    out = tiny_model(tiny_data)
    loss = out.sum()
    loss.backward()

    # At least one parameter should have a non-None, non-zero gradient
    has_grad = any(
        p.grad is not None and p.grad.abs().sum() > 0
        for p in tiny_model.parameters()
    )
    assert has_grad, "No gradients flowed to model parameters"


def test_embed_features_shape(tiny_model: HGAT) -> None:
    """embed_features returns (N, hidden_dim) L2-normalized."""
    torch.manual_seed(1)
    x = torch.randn(3, 896)
    out = tiny_model.embed_features(x)
    assert out.shape == (3, 32), f"Expected (3, 32), got {out.shape}"
    norms = out.norm(dim=-1)
    assert torch.allclose(norms, torch.ones(3), atol=1e-5), (
        f"embed_features row norms not ≈ 1: {norms}"
    )


def test_isolated_node_residual(tiny_model: HGAT) -> None:
    """An isolated garment node's forward() embedding ≈ its embed_features() embedding.

    Garment node at index 5 has no edges in tiny_data. Because of the residual
    connection and add_self_loops=False, the message-passing update is zero, so
    h_L == h0. Thus forward() and embed_features() should agree for this node.
    """
    tiny_model.eval()
    data = make_tiny_graph()  # garment 5 is isolated

    with torch.no_grad():
        graph_emb = tiny_model(data)  # (6, hidden_dim)
        isolated_emb_graph = graph_emb[5]  # (hidden_dim,)

        # embed_features using the raw features of garment 5
        x_isolated = data["garment"].x[5].unsqueeze(0)  # (1, 896)
        cold_emb = tiny_model.embed_features(x_isolated).squeeze(0)  # (hidden_dim,)

    # They should be close
    cosine_sim = float(
        F.cosine_similarity(
            isolated_emb_graph.unsqueeze(0), cold_emb.unsqueeze(0)
        )
    )
    assert cosine_sim > 0.99, (
        f"Isolated node cosine similarity to embed_features: {cosine_sim:.4f} (expected > 0.99)"
    )


def test_forward_different_inputs_differ(tiny_model: HGAT) -> None:
    """Different garment features should produce different embeddings."""
    torch.manual_seed(2)
    data1 = make_tiny_graph()
    data2 = make_tiny_graph()
    data2["garment"].x = torch.randn(6, 896)

    tiny_model.eval()
    with torch.no_grad():
        out1 = tiny_model(data1)
        out2 = tiny_model(data2)

    # At least some embeddings should differ
    assert not torch.allclose(out1, out2, atol=1e-4), (
        "Embeddings from different inputs should differ"
    )
