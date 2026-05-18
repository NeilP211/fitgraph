"""Heterogeneous Graph Attention Network for outfit compatibility."""

from __future__ import annotations

import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch_geometric.data import HeteroData
from torch_geometric.nn import GATConv, HeteroConv


class HGAT(nn.Module):
    """Heterogeneous GAT with a deep nonlinear inductive encoder.

    Architecture
    ------------
    1. ``encoder``: deep MLP applied to raw features for both node types.
       ``Linear(in_dim → 512) → LayerNorm → GELU → Dropout →
         Linear(512 → hidden_dim) → LayerNorm → GELU → Dropout``
       Produces the base item representation ``h = encoder(x)``.
    2. ``num_layers`` of heterogeneous GAT applied with a RESIDUAL:
       ``h = h + dropout(ELU(GATConv_per_relation(h)))``.
    3. Final garment ``h`` is L2-normalised.

    Cold-start / isolated nodes
    ---------------------------
    Because of residuals and add_self_loops=False, a garment with no edges
    receives zero message-passing updates, so ``h_L == encoder(x)``.
    ``embed_features(x)`` returns ``L2_normalize(encoder(x))``, which equals
    ``forward`` on an isolated garment node.  The two paths stay in the same
    representation space.
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
        self.dropout_p = dropout

        mid_dim = 512

        # Deep nonlinear encoder shared by both node types
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, mid_dim),
            nn.LayerNorm(mid_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(mid_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

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

        self.elu = nn.ELU()
        self._init_weights()

    def _init_weights(self) -> None:
        for module in self.encoder.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)

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
        # Encode both node types through the deep MLP
        h_garment = self.encoder(data["garment"].x)
        h_outfit = self.encoder(data["outfit"].x)

        h_dict = {"garment": h_garment, "outfit": h_outfit}

        # Apply GAT layers with residual connections
        for conv in self.convs:
            conv_out = conv(h_dict, data.edge_index_dict)
            new_h_dict: dict[str, Tensor] = {}
            for node_type in h_dict:
                if node_type in conv_out:
                    # Residual: h = h + dropout(ELU(conv_out))
                    delta = F.dropout(
                        self.elu(conv_out[node_type]),
                        p=self.dropout_p,
                        training=self.training,
                    )
                    new_h_dict[node_type] = h_dict[node_type] + delta
                else:
                    new_h_dict[node_type] = h_dict[node_type]
            h_dict = new_h_dict

        return F.normalize(h_dict["garment"], p=2, dim=-1)

    def embed_features(self, x: Tensor) -> Tensor:
        """Embed raw feature vectors without graph context (cold-start / inductive path).

        Returns ``L2_normalize(encoder(x))``.  For an isolated garment node
        (no edges), this is identical to what ``forward`` would return, because
        the GAT residual adds zero message-passing update.

        Parameters
        ----------
        x:
            Raw fused feature vectors of shape ``(N, in_dim)``.

        Returns
        -------
        Tensor
            L2-normalised embeddings of shape ``(N, hidden_dim)``.
        """
        h = self.encoder(x)
        return F.normalize(h, p=2, dim=-1)
