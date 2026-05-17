"""Train the HGAT model on the FitGraph dataset.

Usage
-----
  python scripts/train.py              # use settings defaults (subset, 30 epochs)
  python scripts/train.py --full       # full dataset
  python scripts/train.py --epochs 10  # override epoch count
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch

from fitgraph.config import Settings, resolve_device
from fitgraph.config import settings as default_settings
from fitgraph.graph.builder import load_graph_bundle
from fitgraph.models.hgat import HGAT
from fitgraph.training.trainer import Trainer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train FitGraph HGAT model")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use the full dataset (sets use_full=True in settings)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Override number of training epochs",
    )
    return parser.parse_args()


def align_clip_to_garments(
    garment_ids: list[str],
    npz_ids: np.ndarray,
    clip_emb: np.ndarray,
) -> np.ndarray:
    """Reorder clip_emb rows to match garment_ids order.

    Parameters
    ----------
    garment_ids:
        Ordered list of garment item IDs from the graph bundle.
    npz_ids:
        Item IDs from items.npz (may be in different order).
    clip_emb:
        CLIP embeddings aligned to npz_ids, shape (N, 512).

    Returns
    -------
    np.ndarray
        CLIP embeddings aligned to garment_ids, shape (len(garment_ids), 512).
    """
    id_to_clip: dict[str, np.ndarray] = {
        str(npz_ids[i]): clip_emb[i] for i in range(len(npz_ids))
    }
    dim = clip_emb.shape[1]
    result = np.zeros((len(garment_ids), dim), dtype=np.float32)
    missing = 0
    for i, gid in enumerate(garment_ids):
        if gid in id_to_clip:
            result[i] = id_to_clip[gid]
        else:
            missing += 1
    if missing > 0:
        print(f"[warn] {missing} garment IDs not found in items.npz; using zero CLIP emb.")
    return result


def export_garment_embeddings(
    model: HGAT,
    data: object,
    garment_ids: list[str],
    version_dir: Path,
    device: str,
) -> Path:
    """Run a final forward pass and save garment embeddings to NPZ.

    Parameters
    ----------
    model:
        Trained HGAT model.
    data:
        HeteroData graph (already on device).
    garment_ids:
        List of garment item IDs in node order.
    version_dir:
        Directory to save the NPZ file.
    device:
        Device string.

    Returns
    -------
    Path
        Path to the saved NPZ file.
    """
    model.eval()
    with torch.no_grad():
        emb = model(data)  # (num_garments, hidden_dim)
    emb_np = emb.cpu().numpy().astype(np.float32)
    ids_np = np.array(garment_ids)
    out_path = version_dir / "garment_embeddings.npz"
    np.savez(out_path, ids=ids_np, emb=emb_np)
    print(f"Saved garment embeddings: {out_path}  shape={emb_np.shape}")
    return out_path


def main() -> None:
    args = parse_args()

    # Build settings (override fields as needed)
    settings = default_settings
    if args.full:
        # Re-instantiate with use_full=True
        settings = Settings(use_full=True)
    if args.epochs is not None:
        # Re-instantiate with overridden epochs
        kwargs: dict = {}
        if args.full:
            kwargs["use_full"] = True
        settings = Settings(epochs=args.epochs, **kwargs)

    print(f"Settings: epochs={settings.epochs}, hidden_dim={settings.hidden_dim}")
    print(f"Device: {resolve_device()}")

    # Load graph bundle
    graph_path = settings.graph_dir / "graph.pt"
    print(f"Loading graph from {graph_path} ...")
    bundle = load_graph_bundle(graph_path)
    print(
        f"  garments={len(bundle.garment_ids)}, outfits={len(bundle.outfit_ids)}, "
        f"splits={dict(zip(*np.unique(bundle.outfit_split, return_counts=True), strict=True))}"
    )

    # Load and align CLIP embeddings
    npz_path = settings.embeddings_dir / "items.npz"
    print(f"Loading CLIP embeddings from {npz_path} ...")
    npz = np.load(npz_path)
    aligned_clip = align_clip_to_garments(
        bundle.garment_ids, npz["ids"], npz["clip_emb"]
    )
    print(f"  CLIP emb aligned shape: {aligned_clip.shape}")

    # Create and run trainer
    trainer = Trainer(bundle, aligned_clip, settings)
    print(
        f"Training pairs: {len(trainer._train_pairs)}, "
        f"valid pairs: {len(trainer._valid_pairs)}"
    )
    results = trainer.fit()

    best_auc = results["best_val_auc"]
    version_dir = Path(results["version_dir"])
    print("\nTraining complete!")
    print(f"  Best val AUC: {best_auc:.4f}")
    print(f"  Version dir: {version_dir}")

    # Export garment embeddings from best checkpoint
    device = resolve_device()
    best_model = HGAT(
        in_dim=896,
        hidden_dim=settings.hidden_dim,
        num_layers=settings.num_layers,
        num_heads=settings.num_heads,
        dropout=settings.dropout,
    ).to(device)
    state_dict = torch.load(version_dir / "model.pt", map_location=device, weights_only=True)
    best_model.load_state_dict(state_dict)

    graph_data = bundle.data.to(device)
    export_garment_embeddings(best_model, graph_data, bundle.garment_ids, version_dir, device)

    print(f"\nDone. Best val AUC={best_auc:.4f}, version dir={version_dir}")


if __name__ == "__main__":
    main()
