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
from fitgraph.data.splits import load_splits
from fitgraph.graph.builder import build_hetero_graph
from fitgraph.models.hgat import HGAT
from fitgraph.training.trainer import Trainer

# Polyvore root relative to the project (data/raw/polyvore-outfit-dataset/polyvore_outfits)
_POLYVORE_ROOT = Path("data/raw/polyvore-outfit-dataset/polyvore_outfits")


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


def main() -> None:
    args = parse_args()

    # Build settings (override fields as needed)
    settings = default_settings
    kwargs: dict = {}
    if args.full:
        kwargs["use_full"] = True
    if args.epochs is not None:
        kwargs["epochs"] = args.epochs
    if kwargs:
        settings = Settings(**kwargs)

    print(f"Settings: epochs={settings.epochs}, hidden_dim={settings.hidden_dim}, "
          f"batch_size={settings.batch_size}, edge_dropout={settings.edge_dropout}")
    print(f"Device: {resolve_device()}")

    # ------------------------------------------------------------------
    # 1. Load item embeddings
    # ------------------------------------------------------------------
    npz_path = settings.embeddings_dir / "items.npz"
    print(f"Loading embeddings from {npz_path} ...")
    npz = np.load(npz_path)
    npz_ids: list[str] = [str(x) for x in npz["ids"]]
    fused_np: np.ndarray = npz["fused"].astype(np.float32)     # (N, 896)
    clip_np: np.ndarray = npz["clip_emb"].astype(np.float32)   # (N, 512)
    fused_tensor = torch.from_numpy(fused_np)
    clip_tensor = torch.from_numpy(clip_np)
    print(f"  items: {len(npz_ids)}, fused_dim={fused_np.shape[1]}, clip_dim={clip_np.shape[1]}")

    # ------------------------------------------------------------------
    # 2. Load splits
    # ------------------------------------------------------------------
    subset = None if settings.use_full else settings.subset_outfits
    print(f"Loading splits (subset_outfits={subset}) ...")
    splits = load_splits(_POLYVORE_ROOT, subset_outfits=subset)
    train_outfits = splits["train"]
    valid_outfits = splits["valid"]
    test_outfits = splits["test"]
    print(f"  train={len(train_outfits)}, valid={len(valid_outfits)}, test={len(test_outfits)}")

    # ------------------------------------------------------------------
    # 3. Create and run trainer
    # ------------------------------------------------------------------
    trainer = Trainer(
        fused_tensor=fused_tensor,
        clip_tensor=clip_tensor,
        all_ids=npz_ids,
        train_outfits=train_outfits,
        valid_outfits=valid_outfits,
        settings=settings,
    )
    print(
        f"Valid pos pairs: {len(trainer._valid_pairs)}, "
        f"neg pairs: {len(trainer._valid_neg_pairs)}"
    )

    results = trainer.fit()

    best_auc = results["best_val_auc"]
    version_dir = Path(results["version_dir"])
    print("\nTraining complete!")
    print(f"  Best honest val AUC: {best_auc:.4f}")
    print(f"  Version dir: {version_dir}")

    # ------------------------------------------------------------------
    # 4. Load best checkpoint and export embeddings
    # ------------------------------------------------------------------
    device_str = resolve_device()
    device = torch.device(device_str)

    in_dim = fused_np.shape[1]
    best_model = HGAT(
        in_dim=in_dim,
        hidden_dim=settings.hidden_dim,
        num_layers=settings.num_layers,
        num_heads=settings.num_heads,
        dropout=settings.dropout,
    ).to(device)
    state_dict = torch.load(version_dir / "model.pt", map_location=device, weights_only=True)
    best_model.load_state_dict(state_dict)
    best_model.eval()

    # 4a. catalog_embeddings.npz: TRAIN items via graph forward (leakage-free)
    print("\nExporting catalog embeddings (train items, graph forward) ...")
    id_to_fused: dict[str, np.ndarray] = {iid: fused_np[i] for i, iid in enumerate(npz_ids)}
    train_bundle = build_hetero_graph(
        outfits_by_split={"train": train_outfits},
        item_embeddings=id_to_fused,
    )
    catalog_graph = train_bundle.data.to(device)
    with torch.no_grad():
        catalog_emb = best_model(catalog_graph)  # (num_train_garments, D)
    catalog_ids = np.array(train_bundle.garment_ids)
    catalog_emb_np = catalog_emb.cpu().numpy().astype(np.float32)
    catalog_out = version_dir / "catalog_embeddings.npz"
    np.savez(catalog_out, ids=catalog_ids, emb=catalog_emb_np)
    print(f"  Saved {catalog_out}  shape={catalog_emb_np.shape}")

    # 4b. inductive_embeddings.npz: ALL items via embed_features (no graph)
    print("Exporting inductive embeddings (all items, embed_features) ...")
    fused_dev = fused_tensor.to(device)
    with torch.no_grad():
        inductive_emb = best_model.embed_features(fused_dev)  # (N, D)
    inductive_ids = np.array(npz_ids)
    inductive_emb_np = inductive_emb.cpu().numpy().astype(np.float32)
    inductive_out = version_dir / "inductive_embeddings.npz"
    np.savez(inductive_out, ids=inductive_ids, emb=inductive_emb_np)
    print(f"  Saved {inductive_out}  shape={inductive_emb_np.shape}")

    print(f"\nDone. Best honest val AUC={best_auc:.4f}, version dir={version_dir}")


if __name__ == "__main__":
    main()
