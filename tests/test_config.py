"""Tests for fitgraph.config — Settings defaults and resolve_device."""

from fitgraph.config import Settings, resolve_device


def test_settings_loads_defaults():
    s = Settings()
    assert s.subset_outfits > 0
    assert s.epochs > 0
    assert s.lr > 0
    assert s.batch_size > 0
    assert s.hidden_dim > 0


def test_derived_dirs_are_under_data_dir():
    s = Settings()
    assert s.raw_dir == s.data_dir / "raw"
    assert s.embeddings_dir == s.data_dir / "embeddings"
    assert s.graph_dir == s.data_dir / "graph"
    assert s.models_dir == s.data_dir / "models"


def test_resolve_device_returns_valid_device():
    device = resolve_device()
    assert device in {"mps", "cuda", "cpu"}
