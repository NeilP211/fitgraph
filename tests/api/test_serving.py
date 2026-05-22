"""Tests for api/serving.py — synthetic checkpoint, no real model or dataset."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from fitgraph.api.serving import ModelService, latest_model_dir
from fitgraph.models.hgat import HGAT
from fitgraph.models.type_aware import TypeAwareScorer, TypeSpaceIndex

# ---------------------------------------------------------------------------
# Helpers: build a tiny synthetic checkpoint in a tmp dir
# ---------------------------------------------------------------------------

_TYPESPACES = [
    ("tops", "bottoms"),
    ("tops", "shoes"),
    ("bottoms", "shoes"),
]
_IN_DIM = 896
_HIDDEN = 256
_NUM_LAYERS = 2
_NUM_HEADS = 4


def _make_checkpoint(base: Path) -> Path:
    """Write a minimal valid checkpoint directory and return its path."""
    model_dir = base / "v1"
    model_dir.mkdir(parents=True)

    type_index = TypeSpaceIndex(_TYPESPACES)
    num_spaces = type_index.num_spaces  # 4

    # Build tiny (but correctly-shaped) models
    hgat = HGAT(
        in_dim=_IN_DIM,
        hidden_dim=_HIDDEN,
        num_layers=_NUM_LAYERS,
        num_heads=_NUM_HEADS,
        dropout=0.0,
    )
    scorer = TypeAwareScorer(num_spaces=num_spaces, dim=_HIDDEN)

    torch.save(
        {"hgat": hgat.state_dict(), "scorer": scorer.state_dict()},
        model_dir / "model.pt",
    )

    # type_index.json — include the item_types map so serving.py can load it
    item_types_map = {
        "item_001": "tops",
        "item_002": "bottoms",
        "item_003": "shoes",
    }
    type_index_data = type_index.to_dict()
    type_index_data["item_types"] = item_types_map
    (model_dir / "type_index.json").write_text(json.dumps(type_index_data))

    meta = {
        "version": "v1",
        "in_dim": _IN_DIM,
        "hidden_dim": _HIDDEN,
        "num_layers": _NUM_LAYERS,
        "num_heads": _NUM_HEADS,
        "dropout": 0.0,
        "num_spaces": num_spaces,
    }
    (model_dir / "meta.json").write_text(json.dumps(meta))

    return model_dir


def _make_test_image(path: Path) -> None:
    """Write a tiny random RGB image to *path*."""
    img = Image.fromarray(
        np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8), mode="RGB"
    )
    img.save(path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def checkpoint_dir(tmp_path: Path) -> Path:
    return _make_checkpoint(tmp_path)


@pytest.fixture()
def loaded_service(checkpoint_dir: Path) -> ModelService:
    svc = ModelService()
    svc.load(checkpoint_dir)
    return svc


@pytest.fixture()
def test_image(tmp_path: Path) -> Path:
    img_path = tmp_path / "test.jpg"
    _make_test_image(img_path)
    return img_path


# ---------------------------------------------------------------------------
# latest_model_dir
# ---------------------------------------------------------------------------


class TestLatestModelDir:
    def test_returns_none_when_no_models_dir(self, tmp_path, monkeypatch):
        """Returns None when the models directory does not exist."""
        monkeypatch.setattr(
            "fitgraph.api.serving.settings",
            type("S", (), {"models_dir": tmp_path / "nonexistent"})(),
        )
        assert latest_model_dir() is None

    def test_returns_none_when_dir_is_empty(self, tmp_path, monkeypatch):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        monkeypatch.setattr(
            "fitgraph.api.serving.settings",
            type("S", (), {"models_dir": models_dir})(),
        )
        assert latest_model_dir() is None

    def test_returns_highest_version(self, tmp_path, monkeypatch):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        monkeypatch.setattr(
            "fitgraph.api.serving.settings",
            type("S", (), {"models_dir": models_dir})(),
        )
        # Create v1 and v2, both complete
        for v in (1, 2):
            vdir = models_dir / f"v{v}"
            vdir.mkdir()
            for f in ("model.pt", "meta.json", "type_index.json"):
                (vdir / f).touch()

        result = latest_model_dir()
        assert result is not None
        assert result.name == "v2"

    def test_skips_incomplete_dirs(self, tmp_path, monkeypatch):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        monkeypatch.setattr(
            "fitgraph.api.serving.settings",
            type("S", (), {"models_dir": models_dir})(),
        )
        # v2 exists but is missing type_index.json
        v2 = models_dir / "v2"
        v2.mkdir()
        (v2 / "model.pt").touch()
        (v2 / "meta.json").touch()
        # v1 is complete
        v1 = models_dir / "v1"
        v1.mkdir()
        for f in ("model.pt", "meta.json", "type_index.json"):
            (v1 / f).touch()

        result = latest_model_dir()
        assert result is not None
        assert result.name == "v1"

    def test_discovery_with_real_checkpoint(self, tmp_path, monkeypatch):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        monkeypatch.setattr(
            "fitgraph.api.serving.settings",
            type("S", (), {"models_dir": models_dir})(),
        )
        _make_checkpoint(models_dir)
        result = latest_model_dir()
        assert result is not None
        assert result.name == "v1"


# ---------------------------------------------------------------------------
# ModelService.load
# ---------------------------------------------------------------------------


class TestModelServiceLoad:
    def test_load_sets_version(self, checkpoint_dir: Path):
        svc = ModelService()
        svc.load(checkpoint_dir)
        assert svc.current_version == "v1"

    def test_load_is_loaded(self, checkpoint_dir: Path):
        svc = ModelService()
        assert not svc.is_loaded
        svc.load(checkpoint_dir)
        assert svc.is_loaded

    def test_load_populates_item_types(self, checkpoint_dir: Path):
        svc = ModelService()
        svc.load(checkpoint_dir)
        assert "item_001" in svc._item_types
        assert svc._item_types["item_001"] == "tops"

    def test_load_populates_type_index(self, checkpoint_dir: Path):
        svc = ModelService()
        svc.load(checkpoint_dir)
        assert svc._type_index is not None
        assert svc._type_index.num_spaces == len(_TYPESPACES) + 1

    def test_reload_returns_false_when_no_new_checkpoint(
        self, checkpoint_dir: Path, monkeypatch
    ):
        models_dir = checkpoint_dir.parent
        monkeypatch.setattr(
            "fitgraph.api.serving.settings",
            type("S", (), {"models_dir": models_dir})(),
        )
        svc = ModelService()
        svc.load(checkpoint_dir)
        # Same dir — reload should return False
        assert svc.reload() is False


# ---------------------------------------------------------------------------
# ModelService.score
# ---------------------------------------------------------------------------


class TestModelServiceScore:
    def test_score_returns_float_in_range(self, loaded_service: ModelService):
        rng = np.random.default_rng(0)
        emb_a = rng.standard_normal(256).astype(np.float32)
        emb_b = rng.standard_normal(256).astype(np.float32)
        # L2-normalise
        emb_a /= np.linalg.norm(emb_a) + 1e-12
        emb_b /= np.linalg.norm(emb_b) + 1e-12

        s = loaded_service.score(emb_a, "tops", emb_b, "bottoms")
        assert isinstance(s, float)
        assert -1.0 <= s <= 1.0

    def test_score_known_pair(self, loaded_service: ModelService):
        """Identical embeddings in any subspace should yield score ≈ 1.0."""
        rng = np.random.default_rng(1)
        emb = rng.standard_normal(256).astype(np.float32)
        emb /= np.linalg.norm(emb) + 1e-12
        s = loaded_service.score(emb, "tops", emb, "bottoms")
        # With uniform masks at init (softplus(1) ≈ constant), same emb → cosine ≈ 1
        assert s > 0.99

    def test_score_unknown_types_uses_fallback(self, loaded_service: ModelService):
        rng = np.random.default_rng(2)
        emb = rng.standard_normal(256).astype(np.float32)
        emb /= np.linalg.norm(emb) + 1e-12
        # Unknown types should not raise
        s = loaded_service.score(emb, "hats", emb, "scarves")
        assert -1.0 <= s <= 1.0

    def test_score_raises_when_not_loaded(self):
        svc = ModelService()
        emb = np.zeros(256, dtype=np.float32)
        with pytest.raises(RuntimeError, match="not been loaded"):
            svc.score(emb, "tops", emb, "bottoms")


# ---------------------------------------------------------------------------
# ModelService.embed_image
# ---------------------------------------------------------------------------


class TestModelServiceEmbedImage:
    def test_embed_image_shape(self, loaded_service: ModelService, test_image: Path):
        emb = loaded_service.embed_image(test_image)
        assert emb.shape == (256,)

    def test_embed_image_dtype(self, loaded_service: ModelService, test_image: Path):
        emb = loaded_service.embed_image(test_image)
        assert emb.dtype == np.float32

    def test_embed_image_is_normalized(self, loaded_service: ModelService, test_image: Path):
        emb = loaded_service.embed_image(test_image)
        norm = float(np.linalg.norm(emb))
        assert abs(norm - 1.0) < 1e-5

    def test_embed_image_with_text(self, loaded_service: ModelService, test_image: Path):
        emb = loaded_service.embed_image(test_image, text="blue cotton shirt")
        assert emb.shape == (256,)
        assert abs(float(np.linalg.norm(emb)) - 1.0) < 1e-5

    def test_embed_image_raises_when_not_loaded(self, test_image: Path):
        svc = ModelService()
        with pytest.raises(RuntimeError, match="not been loaded"):
            svc.embed_image(test_image)


# ---------------------------------------------------------------------------
# ModelService.suggest_by_categories
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _pg_engine():
    """Connect to Postgres for suggest_by_categories tests; skip if unavailable."""
    try:
        from sqlalchemy import text  # noqa: PLC0415
        from sqlalchemy.exc import OperationalError  # noqa: PLC0415

        from fitgraph.db.session import apply_schema, get_engine  # noqa: PLC0415

        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        apply_schema(eng)
        return eng
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


@pytest.fixture()
def _pg_session(_pg_engine):
    """Session rolled back after each test."""
    from fitgraph.db.session import get_session  # noqa: PLC0415

    factory = get_session(_pg_engine)
    sess = factory()
    sess.begin_nested()
    yield sess
    sess.rollback()
    sess.close()


def _seed_item_cat(session, item_id: str, title: str, cat: str) -> None:
    from sqlalchemy import text  # noqa: PLC0415

    session.execute(
        text(
            """
            INSERT INTO items (id, title, description, semantic_category,
                               tags, search_doc, image_path)
            VALUES (:id, :title, '', :cat,
                    ARRAY[:cat]::text[],
                    to_tsvector('english', :title || ' ' || :cat), '')
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": item_id, "title": title, "cat": cat},
    )
    session.flush()


def _seed_emb(session, item_id: str, vec: list[float]) -> None:
    from fitgraph.retrieval.pgvector_store import upsert_embeddings  # noqa: PLC0415

    upsert_embeddings(session, [(item_id, vec)], model_version="v1")


def _rand_emb(seed: int = 0) -> list[float]:
    import numpy as np  # noqa: PLC0415

    rng = np.random.default_rng(seed)
    v = rng.standard_normal(256).astype(np.float32)
    v /= np.linalg.norm(v) + 1e-12
    return v.tolist()


class TestSuggestByCategories:
    def test_suggest_excludes_seed_category(self, loaded_service: ModelService, _pg_session):
        _seed_item_cat(_pg_session, "zqxsbc_seed", "seed top", "zqxsbc_tops")
        _seed_emb(_pg_session, "zqxsbc_seed", _rand_emb(10))

        for i in range(3):
            _seed_item_cat(_pg_session, f"zqxsbc_bot_{i}", f"bottom {i}", "zqxsbc_bottoms")
            _seed_emb(_pg_session, f"zqxsbc_bot_{i}", _rand_emb(i + 20))
        for i in range(3):
            _seed_item_cat(_pg_session, f"zqxsbc_shoe_{i}", f"shoe {i}", "zqxsbc_shoes")
            _seed_emb(_pg_session, f"zqxsbc_shoe_{i}", _rand_emb(i + 30))
        _pg_session.flush()

        out = loaded_service.suggest_by_categories("zqxsbc_seed", _pg_session, per_category=2)

        assert out["seed"]["item_id"] == "zqxsbc_seed"
        # Seed's own category must not appear in suggestions
        assert "zqxsbc_tops" not in out["suggestions"]

    def test_per_category_cap(self, loaded_service: ModelService, _pg_session):
        _seed_item_cat(_pg_session, "zqxsbc_cap_seed", "cap seed", "zqxsbc_cap_tops")
        _seed_emb(_pg_session, "zqxsbc_cap_seed", _rand_emb(40))

        for i in range(5):
            _seed_item_cat(_pg_session, f"zqxsbc_cap_bot_{i}", f"bot {i}", "zqxsbc_cap_bottoms")
            _seed_emb(_pg_session, f"zqxsbc_cap_bot_{i}", _rand_emb(i + 50))
        _pg_session.flush()

        out = loaded_service.suggest_by_categories("zqxsbc_cap_seed", _pg_session, per_category=2)
        assert all(len(v) <= 2 for v in out["suggestions"].values())

    def test_items_belong_to_correct_category(self, loaded_service: ModelService, _pg_session):
        _seed_item_cat(_pg_session, "zqxsbc_cat_seed", "cat seed", "zqxsbc_cat_tops")
        _seed_emb(_pg_session, "zqxsbc_cat_seed", _rand_emb(60))

        for i in range(2):
            _seed_item_cat(_pg_session, f"zqxsbc_cat_bot_{i}", f"bot {i}", "zqxsbc_cat_bottoms")
            _seed_emb(_pg_session, f"zqxsbc_cat_bot_{i}", _rand_emb(i + 70))
        _pg_session.flush()

        out = loaded_service.suggest_by_categories("zqxsbc_cat_seed", _pg_session, per_category=4)

        for cat, items in out["suggestions"].items():
            assert all(it["semantic_category"] == cat for it in items)

    def test_missing_seed_raises_key_error(self, loaded_service: ModelService, _pg_session):
        with pytest.raises(KeyError):
            loaded_service.suggest_by_categories("zqxsbc_nonexistent_xyz", _pg_session)
