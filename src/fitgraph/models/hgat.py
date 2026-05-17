"""Heterogeneous Graph Attention Network for outfit compatibility."""

from __future__ import annotations

import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch_geometric.data import HeteroData
from torch_geometric.nn import GATConv, HeteroConv


class HGAT(nn.Module):
    """Heterogeneous GAT with residual connections for garment embedding.

    Architecture
    ------------
    1. ``input_proj``: Linear(in_dim, hidden_dim) applied to both garment and outfit
       node features. ``h0 = input_proj(x)``.
    2. ``num_layers`` of heterogeneous GAT: each layer is a HeteroConv over the two
       relations, each using GATConv(hidden_dim, hidden_dim, heads=num_heads,
       concat=False, add_self_loops=False). Applied with a residual:
       ``h = h + ELU(conv(h, edge_index_dict))`` then dropout.
    3. ``out_head``: Linear(hidden_dim, hidden_dim) producing the final garment
       embedding, L2-normalised.

    Cold-start / isolated nodes
    ---------------------------
    Because of residuals and add_self_loops=False, a garment with no edges has
    h_L == h0. So ``embed_features(x)`` (which computes out_head(input_proj(x)))
    is in the same representation space as full-graph embeddings.
    """

    def __init__(
        self,
        in_dim: int = 896,
        hidden_dim: int = 256,
        num_layers: int = 2,
        num_heads: int = 4,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout = dropout

        # Shared input projection for both node types
        self.input_proj = nn.Linear(in_dim, hidden_dim)

        # Stack of HeteroConv layers
        self.convs = nn.ModuleList()
        for _ in range(num_layers):
            conv = HeteroConv(
                {
                    ("garment", "in", "outfit"): GATConv(
                        hidden_dim,
                        hidden_dim,
                        heads=num_heads,
                        concat=False,
                        add_self_loops=False,
                        dropout=dropout,
                    ),
                    ("outfit", "contains", "garment"): GATConv(
                        hidden_dim,
                        hidden_dim,
                        heads=num_heads,
                        concat=False,
                        add_self_loops=False,
                        dropout=dropout,
                    ),
                }
            )
            self.convs.append(conv)

        # Output head
        self.out_head = nn.Linear(hidden_dim, hidden_dim)

        self.elu = nn.ELU()
        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.xavier_uniform_(self.input_proj.weight)
        nn.init.zeros_(self.input_proj.bias)
        nn.init.xavier_uniform_(self.out_head.weight)
        nn.init.zeros_(self.out_head.bias)

    def forward(self, data: HeteroData) -> Tensor:
        """Full-graph forward pass.

        Parameters
        ----------
        data:
            HeteroData with 'garment' and 'outfit' node types.

        Returns
        -------
        Tensor
            L2-normalised garment embeddings of shape ``(num_garments, hidden_dim)``.
        """
        # Project both node types into hidden space
        h_garment = self.input_proj(data["garment"].x)
        h_outfit = self.input_proj(data["outfit"].x)

        h_dict = {"garment": h_garment, "outfit": h_outfit}

        # Apply GAT layers with residual connections
        for conv in self.convs:
            conv_out = conv(h_dict, data.edge_index_dict)
            # Residual: h = h + ELU(conv_out), then dropout
            new_h_dict: dict[str, Tensor] = {}
            for node_type in h_dict:
                if node_type in conv_out:
                    new_h_dict[node_type] = h_dict[node_type] + self.elu(
                        conv_out[node_type]
                    )
                else:
                    new_h_dict[node_type] = h_dict[node_type]
            # Apply dropout to all node types
            h_dict = {
                k: F.dropout(v, p=self.dropout, training=self.training)
                for k, v in new_h_dict.items()
            }

        # Output head on garment embeddings only
        z = self.out_head(h_dict["garment"])
        return F.normalize(z, p=2, dim=-1)

    def embed_features(self, x: Tensor) -> Tensor:
        """Embed raw feature vectors without graph context (cold-start path).

        Computes ``out_head(input_proj(x))``, L2-normalised. This is equivalent
        to the full-graph path for an isolated garment node (no edges = no
        message passing, so h_L == h0 due to residuals).

        Parameters
        ----------
        x:
            Raw fused feature vectors of shape ``(N, in_dim)``.

        Returns
        -------
        Tensor
            L2-normalised embeddings of shape ``(N, hidden_dim)``.
        """
        h = self.input_proj(x)
        z = self.out_head(h)
        return F.normalize(z, p=2, dim=-1)
