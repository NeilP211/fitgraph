"""Tests for the Trainer class."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import torch
from torch_geometric.data import HeteroData

from fitgraph.config import Settings
from fitgraph.graph.builder import GraphBundle
from fitgraph.training.trainer import Trainer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_synthetic_bundle(
    num_garments: int = 40,
    num_outfits: int = 20,
    items_per_outfit: int = 4,
    seed: int = 0,
) -> tuple[GraphBundle, np.ndarray]:
    """Build a tiny synthetic GraphBundle + CLIP embeddings for testing."""
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)

    data = HeteroData()
    data["garment"].x = torch.randn(num_garments, 896)
    data["outfit"].x = torch.zeros(num_outfits, 896)

    src_g: list[int] = []
    dst_o: list[int] = []
    for o_idx in range(num_outfits):
        # Pick `items_per_outfit` garments for this outfit
        chosen = rng.choice(num_garments, size=items_per_outfit, replace=False).tolist()
        for g_idx in chosen:
            src_g.append(g_idx)
            dst_o.append(o_idx)

    data["garment", "in", "outfit"].edge_index = torch.tensor(
        [src_g, dst_o], dtype=torch.long
    )
    data["outfit", "contains", "garment"].edge_index = torch.tensor(
        [dst_o, src_g], dtype=torch.long
    )

    garment_ids = [f"g{i}" for i in range(num_garments)]
    outfit_ids = [f"o{i}" for i in range(num_outfits)]
    # Assign splits: 60% train, 20% valid, 20% test
    outfit_split: list[str] = []
    for i in range(num_outfits):
        if i < int(0.6 * num_outfits):
            outfit_split.append("train")
        elif i < int(0.8 * num_outfits):
            outfit_split.append("valid")
        else:
            outfit_split.append("test")

    bundle = GraphBundle(
        data=data,
        garment_ids=garment_ids,
        outfit_ids=outfit_ids,
        outfit_split=outfit_split,
    )

    # Synthetic CLIP embeddings aligned to garment order
    clip_emb = rng.standard_normal((num_garments, 512)).astype(np.float32)
    clip_emb /= np.linalg.norm(clip_emb, axis=-1, keepdims=True) + 1e-8

    return bundle, clip_emb


def _make_settings(models_dir: Path) -> Settings:
    """Create a minimal Settings for testing."""
    return Settings(
        data_dir=models_dir.parent,  # just needs to resolve models_dir
        epochs=2,
        batch_size=16,
        hidden_dim=32,
        num_heads=2,
        num_layers=1,
        dropout=0.0,
        lr=1e-3,
        temperature=0.1,
        num_hard_negatives=2,
        seed=42,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trainer_completes_and_saves_checkpoint() -> None:
    """Trainer.fit() completes 2 epochs and writes model.pt + meta.json."""
    bundle, clip_emb = _make_synthetic_bundle()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        settings = _make_settings(tmp_path)
        # Override models_dir by monkey-patching
        settings.__dict__["_models_dir_override"] = tmp_path / "models"

        # Patch the models_dir property via a local subclass
        class PatchedSettings(Settings):
            @property
            def models_dir(self) -> Path:
                return tmp_path / "models"

        patched = PatchedSettings(
            data_dir=tmp_path,
            epochs=2,
            batch_size=16,
            hidden_dim=32,
            num_heads=2,
            num_layers=1,
            dropout=0.0,
            lr=1e-3,
            temperature=0.1,
            num_hard_negatives=2,
            seed=42,
        )

        trainer = Trainer(bundle, clip_emb, patched)
        results = trainer.fit()

        # Check result structure
        assert "best_val_auc" in results
        assert "version_dir" in results
        assert "epoch_losses" in results

        version_dir = Path(results["version_dir"])
        assert version_dir.exists(), f"Version dir not created: {version_dir}"
        assert (version_dir / "model.pt").exists(), "model.pt not saved"
        assert (version_dir / "meta.json").exists(), "meta.json not saved"


def test_trainer_loss_is_finite() -> None:
    """All epoch losses are finite numbers."""
    bundle, clip_emb = _make_synthetic_bundle()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        class PatchedSettings(Settings):
            @property
            def models_dir(self) -> Path:
                return tmp_path / "models"

        patched = PatchedSettings(
            data_dir=tmp_path,
            epochs=2,
            batch_size=16,
            hidden_dim=32,
            num_heads=2,
            num_layers=1,
            dropout=0.0,
            lr=1e-3,
            temperature=0.1,
            num_hard_negatives=2,
            seed=42,
        )

        trainer = Trainer(bundle, clip_emb, patched)
        results = trainer.fit()

        for i, loss in enumerate(results["epoch_losses"]):
            assert math.isfinite(loss), f"Epoch {i+1} loss is not finite: {loss}"


def test_trainer_checkpoint_contents() -> None:
    """model.pt contains a valid state dict and meta.json has expected keys."""
    import json

    bundle, clip_emb = _make_synthetic_bundle()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        class PatchedSettings(Settings):
            @property
            def models_dir(self) -> Path:
                return tmp_path / "models"

        patched = PatchedSettings(
            data_dir=tmp_path,
            epochs=2,
            batch_size=16,
            hidden_dim=32,
            num_heads=2,
            num_layers=1,
            dropout=0.0,
            lr=1e-3,
            temperature=0.1,
            num_hard_negatives=2,
            seed=42,
        )

        trainer = Trainer(bundle, clip_emb, patched)
        results = trainer.fit()

        version_dir = Path(results["version_dir"])

        # Check state dict is loadable
        state = torch.load(version_dir / "model.pt", weights_only=True)
        assert isinstance(state, dict), "model.pt should be a state dict"
        assert len(state) > 0, "State dict is empty"

        # Check meta.json
        meta = json.loads((version_dir / "meta.json").read_text())
        expected_keys = {
            "version", "epochs", "best_val_auc", "hidden_dim",
            "num_layers", "num_heads", "in_dim", "timestamp",
        }
        assert expected_keys.issubset(meta.keys()), (
            f"meta.json missing keys: {expected_keys - meta.keys()}"
        )
        assert meta["hidden_dim"] == 32
        assert meta["in_dim"] == 896


def test_trainer_val_auc_reasonable() -> None:
    """After 2 epochs on synthetic data, val AUC should be a valid probability in [0,1]."""
    bundle, clip_emb = _make_synthetic_bundle()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        class PatchedSettings(Settings):
            @property
            def models_dir(self) -> Path:
                return tmp_path / "models"

        patched = PatchedSettings(
            data_dir=tmp_path,
            epochs=2,
            batch_size=16,
            hidden_dim=32,
            num_heads=2,
            num_layers=1,
            dropout=0.0,
            lr=1e-3,
            temperature=0.1,
            num_hard_negatives=2,
            seed=42,
        )

        trainer = Trainer(bundle, clip_emb, patched)
        results = trainer.fit()

        auc = results["best_val_auc"]
        assert 0.0 <= auc <= 1.0, f"Val AUC out of range [0,1]: {auc}"
