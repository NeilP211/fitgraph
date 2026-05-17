"""Bipartite hetero graph builder for FitGraph.

Constructs a single HeteroData graph containing garment and outfit nodes from
all dataset splits.  Split labels are stored on outfit nodes so the trainer can
restrict the contrastive loss to train-split outfits without re-building the
graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch_geometric.data import HeteroData

from fitgraph.data.polyvore import Outfit


@dataclass
class GraphBundle:
    """Container for a built HeteroData graph and its index maps.

    Attributes
    ----------
    data:
        PyG HeteroData with node types ``'garment'`` and ``'outfit'``, and
        edge types ``('garment', 'in', 'outfit')`` plus
        ``('outfit', 'contains', 'garment')``.
    garment_ids:
        List of item_id strings in garment node order (index → item_id).
    outfit_ids:
        List of set_id strings in outfit node order (index → set_id).
    outfit_split:
        List of split labels (``"train"``/``"valid"``/``"test"``) in outfit
        node order, parallel to ``outfit_ids``.
    """

    data: HeteroData
    garment_ids: list[str]
    outfit_ids: list[str]
    outfit_split: list[str]


def build_hetero_graph(
    outfits_by_split: dict[str, list[Outfit]],
    item_embeddings: dict[str, np.ndarray],
) -> GraphBundle:
    """Build a bipartite HeteroData graph from outfits and item embeddings.

    Parameters
    ----------
    outfits_by_split:
        Mapping of split name (``"train"``, ``"valid"``, ``"test"``) to a list
        of :class:`~fitgraph.data.polyvore.Outfit` objects.
    item_embeddings:
        Mapping of item_id → fused embedding array of shape ``(896,)``.

    Returns
    -------
    :class:`GraphBundle`
        Populated graph bundle.  Outfits whose valid-item count drops below 2
        after filtering to embedded items are silently dropped.
    """
    embed_dim = next(iter(item_embeddings.values())).shape[0] if item_embeddings else 896

    # ------------------------------------------------------------------ #
    # 1. Collect garment nodes: items that appear in ≥1 outfit AND have   #
    #    an embedding.                                                     #
    # ------------------------------------------------------------------ #
    used_item_ids: set[str] = set()
    for outfits in outfits_by_split.values():
        for outfit in outfits:
            for item_id in outfit.item_ids:
                if item_id in item_embeddings:
                    used_item_ids.add(item_id)

    garment_ids: list[str] = sorted(used_item_ids)
    garment_index: dict[str, int] = {iid: idx for idx, iid in enumerate(garment_ids)}

    # ------------------------------------------------------------------ #
    # 2. Filter outfits (need ≥2 valid items) and build outfit lists.     #
    # ------------------------------------------------------------------ #
    outfit_ids: list[str] = []
    outfit_split: list[str] = []
    # Parallel list of valid item_id lists for each surviving outfit
    outfit_valid_items: list[list[str]] = []

    dropped = 0
    for split_name, outfits in outfits_by_split.items():
        for outfit in outfits:
            valid = [iid for iid in outfit.item_ids if iid in garment_index]
            if len(valid) < 2:
                dropped += 1
                continue
            outfit_ids.append(outfit.id)
            outfit_split.append(split_name)
            outfit_valid_items.append(valid)

    # ------------------------------------------------------------------ #
    # 3. Build feature tensors.                                           #
    # ------------------------------------------------------------------ #
    num_garments = len(garment_ids)
    num_outfits = len(outfit_ids)

    # Garment features: stack embeddings in garment_ids order
    garment_x = torch.zeros((num_garments, embed_dim), dtype=torch.float32)
    for idx, iid in enumerate(garment_ids):
        garment_x[idx] = torch.from_numpy(item_embeddings[iid].astype(np.float32))

    # Outfit features: placeholder zeros (learned via message passing)
    outfit_x = torch.zeros((num_outfits, embed_dim), dtype=torch.float32)

    # ------------------------------------------------------------------ #
    # 4. Build edge index for ('garment', 'in', 'outfit').               #
    # ------------------------------------------------------------------ #
    src_garment: list[int] = []
    dst_outfit: list[int] = []

    for outfit_idx, valid_items in enumerate(outfit_valid_items):
        for iid in valid_items:
            src_garment.append(garment_index[iid])
            dst_outfit.append(outfit_idx)

    if src_garment:
        garment_in_outfit = torch.tensor([src_garment, dst_outfit], dtype=torch.long)
        outfit_contains_garment = torch.tensor([dst_outfit, src_garment], dtype=torch.long)
    else:
        garment_in_outfit = torch.zeros((2, 0), dtype=torch.long)
        outfit_contains_garment = torch.zeros((2, 0), dtype=torch.long)

    # ------------------------------------------------------------------ #
    # 5. Assemble HeteroData.                                             #
    # ------------------------------------------------------------------ #
    data = HeteroData()

    data["garment"].x = garment_x
    data["outfit"].x = outfit_x

    data["garment", "in", "outfit"].edge_index = garment_in_outfit
    data["outfit", "contains", "garment"].edge_index = outfit_contains_garment

    # Store dropped count as metadata (informational)
    data["outfit"].num_dropped = dropped

    return GraphBundle(
        data=data,
        garment_ids=garment_ids,
        outfit_ids=outfit_ids,
        outfit_split=outfit_split,
    )


def save_graph_bundle(bundle: GraphBundle, path: Path) -> None:
    """Persist a :class:`GraphBundle` to *path* using :func:`torch.save`.

    Parameters
    ----------
    bundle:
        The bundle to save.
    path:
        Destination file path.  Parent directories are created if needed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "data": bundle.data,
        "garment_ids": bundle.garment_ids,
        "outfit_ids": bundle.outfit_ids,
        "outfit_split": bundle.outfit_split,
    }
    torch.save(payload, path)


def load_graph_bundle(path: Path) -> GraphBundle:
    """Load a :class:`GraphBundle` previously saved with :func:`save_graph_bundle`.

    Parameters
    ----------
    path:
        Source file path.

    Returns
    -------
    :class:`GraphBundle`
    """
    payload = torch.load(Path(path), weights_only=False)
    return GraphBundle(
        data=payload["data"],
        garment_ids=payload["garment_ids"],
        outfit_ids=payload["outfit_ids"],
        outfit_split=payload["outfit_split"],
    )
