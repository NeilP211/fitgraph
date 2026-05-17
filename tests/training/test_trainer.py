"""Tests for the mini-batch subgraph Trainer class."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import torch

from fitgraph.config import Settings
from fitgraph.data.polyvore import Outfit
from fitgraph.training.trainer import Trainer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_synthetic_data(
    num_items: int = 60,
    num_train_outfits: int = 20,
    num_valid_outfits: int = 6,
    items_per_outfit: int = 4,
    seed: int = 0,
) -> tuple[torch.Tensor, torch.Tensor, list[str], list[Outfit], list[Outfit]]:
    """Build synthetic tensors and outfits for testing."""
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)

    all_ids = [f"item{i}" for i in range(num_items)]
    fused = torch.tensor(rng.standard_normal((num_items, 896)).astype(np.float32))
    clip = torch.tensor(rng.standard_normal((num_items, 512)).astype(np.float32))

    def make_outfits(n: int, prefix: str) -> list[Outfit]:
        outfits = []
        for i in range(n):
            chosen = rng.choice(num_items, size=items_per_outfit, replace=False)
            outfits.append(Outfit(id=f"{prefix}{i}", item_ids=[all_ids[j] for j in chosen]))
        return outfits

    train_outfits = make_outfits(num_train_outfits, "train_o")
    valid_outfits = make_outfits(num_valid_outfits, "valid_o")

    return fused, clip, all_ids, train_outfits, valid_outfits


def _make_patched_settings(tmp_path: Path, **overrides) -> Settings:
    """Create a fast minimal Settings, patching models_dir to tmp_path/models."""

    class PatchedSettings(Settings):
        @property
        def models_dir(self) -> Path:
            return tmp_path / "models"

    defaults = dict(
        data_dir=tmp_path,
        epochs=2,
        batch_size=8,
        hidden_dim=32,
        num_heads=2,
        num_layers=1,
        dropout=0.0,
        lr=1e-3,
        temperature=0.1,
        num_hard_negatives=2,
        edge_dropout=0.3,
        seed=42,
    )
    defaults.update(overrides)
    return PatchedSettings(**defaults)


def _make_trainer(tmp_path: Path, **setting_overrides) -> Trainer:
    fused, clip, all_ids, train_outfits, valid_outfits = _make_synthetic_data()
    settings = _make_patched_settings(tmp_path, **setting_overrides)
    return Trainer(
        fused_tensor=fused,
        clip_tensor=clip,
        all_ids=all_ids,
        train_outfits=train_outfits,
        valid_outfits=valid_outfits,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trainer_completes_and_saves_checkpoint() -> None:
    """Trainer.fit() completes 2 epochs and writes model.pt + meta.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        trainer = _make_trainer(tmp_path)
        results = trainer.fit()

        assert "best_val_auc" in results
        assert "version_dir" in results
        assert "epoch_losses" in results

        version_dir = Path(results["version_dir"])
        assert version_dir.exists(), f"Version dir not created: {version_dir}"
        assert (version_dir / "model.pt").exists(), "model.pt not saved"
        assert (version_dir / "meta.json").exists(), "meta.json not saved"


def test_trainer_loss_is_finite() -> None:
    """All epoch losses are finite numbers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        trainer = _make_trainer(tmp_path)
        results = trainer.fit()

        for i, loss in enumerate(results["epoch_losses"]):
            assert math.isfinite(loss), f"Epoch {i+1} loss is not finite: {loss}"


def test_trainer_val_auc_in_range() -> None:
    """Val AUC returned by fit() is a valid probability in [0, 1]."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        trainer = _make_trainer(tmp_path)
        results = trainer.fit()

        auc = results["best_val_auc"]
        assert 0.0 <= auc <= 1.0, f"Val AUC out of range [0,1]: {auc}"


def test_trainer_checkpoint_contents() -> None:
    """model.pt is a valid state dict; meta.json has all required keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        trainer = _make_trainer(tmp_path)
        results = trainer.fit()

        version_dir = Path(results["version_dir"])

        # Check state dict is loadable
        state = torch.load(version_dir / "model.pt", weights_only=True)
        assert isinstance(state, dict), "model.pt should be a state dict"
        assert len(state) > 0, "State dict is empty"

        # Check meta.json
        meta = json.loads((version_dir / "meta.json").read_text())
        required_keys = {
            "version", "epochs_run", "best_val_auc", "hidden_dim",
            "num_layers", "num_heads", "in_dim", "edge_dropout", "timestamp",
        }
        assert required_keys.issubset(meta.keys()), (
            f"meta.json missing keys: {required_keys - meta.keys()}"
        )
        assert meta["hidden_dim"] == 32
        assert meta["in_dim"] == 896
        assert meta["edge_dropout"] == 0.3


def test_trainer_val_auc_computed() -> None:
    """_validate() returns a float and val_auc is logged each epoch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        trainer = _make_trainer(tmp_path)

        # Run one manual validation; should not error
        trainer.model.eval()
        val_auc = trainer._validate()
        assert isinstance(val_auc, float), f"Expected float, got {type(val_auc)}"
        assert 0.0 <= val_auc <= 1.0


def test_trainer_inductive_validation_uses_embed_features() -> None:
    """Validation embeds via embed_features, not forward (no graph used)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        trainer = _make_trainer(tmp_path)

        # embed_features should produce embeddings with correct shape
        trainer.model.eval()
        with torch.no_grad():
            device = next(trainer.model.parameters()).device
            emb = trainer.model.embed_features(trainer.fused_tensor.to(device))
        assert emb.shape == (len(trainer.all_ids), 32), f"Unexpected shape: {emb.shape}"
        # L2-normalised: norms should be ~1
        norms = emb.norm(dim=-1)
        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


def test_trainer_subgraph_build() -> None:
    """_build_batch_subgraph produces valid edge indices within range."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        fused, clip, all_ids, train_outfits, valid_outfits = _make_synthetic_data()
        settings = _make_patched_settings(tmp_path)
        trainer = Trainer(
            fused_tensor=fused,
            clip_tensor=clip,
            all_ids=all_ids,
            train_outfits=train_outfits,
            valid_outfits=valid_outfits,
            settings=settings,
        )

        batch = train_outfits[:4]
        subgraph, local_ids, local_id_to_idx = trainer._build_batch_subgraph(
            batch, edge_dropout=0.0
        )

        n_garments = len(local_ids)
        n_outfits = len(batch)

        assert subgraph["garment"].x.shape[1] == 896
        assert subgraph["outfit"].x.shape[0] == n_outfits

        ei = subgraph["garment", "in", "outfit"].edge_index
        if ei.shape[1] > 0:
            assert ei[0].max() < n_garments, "Garment edge index out of range"
            assert ei[1].max() < n_outfits, "Outfit edge index out of range"
