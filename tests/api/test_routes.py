"""Tests for api/routes.py — TestClient-based, synthetic model + DB data.

DB-dependent tests skip gracefully when Postgres is unreachable.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from fitgraph.api.main import create_app
from fitgraph.api.serving import ModelService
from fitgraph.models.hgat import HGAT
from fitgraph.models.type_aware import TypeAwareScorer, TypeSpaceIndex

# ---------------------------------------------------------------------------
# Helpers — synthetic checkpoint
# ---------------------------------------------------------------------------

_TYPESPACES = [("tops", "bottoms"), ("tops", "shoes"), ("bottoms", "shoes")]
_IN_DIM = 896
_HIDDEN = 256


def _build_checkpoint(base: Path) -> Path:
    vdir = base / "models" / "v1"
    vdir.mkdir(parents=True)

    type_index = TypeSpaceIndex(_TYPESPACES)
    hgat = HGAT(in_dim=_IN_DIM, hidden_dim=_HIDDEN, num_layers=2, num_heads=4, dropout=0.0)
    scorer = TypeAwareScorer(num_spaces=type_index.num_spaces, dim=_HIDDEN)

    torch.save({"hgat": hgat.state_dict(), "scorer": scorer.state_dict()}, vdir / "model.pt")

    type_index_data = type_index.to_dict()
    type_index_data["item_types"] = {"item_001": "tops", "item_002": "bottoms"}
    (vdir / "type_index.json").write_text(json.dumps(type_index_data))
    (vdir / "meta.json").write_text(
        json.dumps(
            {
                "version": "v1",
                "in_dim": _IN_DIM,
                "hidden_dim": _HIDDEN,
                "num_layers": 2,
                "num_heads": 4,
                "dropout": 0.0,
                "num_spaces": type_index.num_spaces,
            }
        )
    )
    return vdir


def _make_image_bytes() -> bytes:
    img = Image.fromarray(np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8), mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _random_emb() -> list[float]:
    v = np.random.default_rng(42).standard_normal(256).astype(np.float32)
    v /= np.linalg.norm(v) + 1e-12
    return v.tolist()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine_and_schema():
    """Connect to Postgres and apply schema; skip module if unavailable."""
    try:
        from fitgraph.db.session import apply_schema, get_engine  # noqa: PLC0415

        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        apply_schema(eng)
        return eng
    except (OperationalError, Exception) as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


@pytest.fixture()
def db_session(engine_and_schema):
    """Session that rolls back after each test."""
    from fitgraph.db.session import get_session  # noqa: PLC0415

    factory = get_session(engine_and_schema)
    sess = factory()
    sess.begin_nested()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture(scope="module")
def checkpoint(tmp_path_factory):
    base = tmp_path_factory.mktemp("ckpt")
    return _build_checkpoint(base)


@pytest.fixture()
def loaded_svc(checkpoint: Path) -> ModelService:
    svc = ModelService()
    svc.load(checkpoint)
    return svc


@pytest.fixture()
def client(loaded_svc: ModelService, db_session):
    """TestClient with the model loaded and a live (rolled-back) DB session."""
    from fastapi.testclient import TestClient  # noqa: PLC0415


    app = create_app()

    # Override DB dependency to use the rolled-back session
    from fitgraph.api.routes import _get_db  # noqa: PLC0415

    def _override_db():
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    # Override model service dependency
    from fitgraph.api.routes import _get_svc  # noqa: PLC0415

    app.dependency_overrides[_get_db] = _override_db
    app.dependency_overrides[_get_svc] = lambda: loaded_svc

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture()
def client_no_model(db_session):
    """TestClient with NO model loaded."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    app = create_app()
    from fitgraph.api.routes import _get_db, _get_svc  # noqa: PLC0415

    def _override_db():
        yield db_session

    app.dependency_overrides[_get_db] = _override_db
    app.dependency_overrides[_get_svc] = lambda: ModelService()  # not loaded

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: seed catalog items into the DB
# ---------------------------------------------------------------------------


def _seed_item(session, item_id: str, title: str, cat: str) -> None:
    session.execute(
        text(
            """
            INSERT INTO items (id, title, description, semantic_category,
                               tags, search_doc, image_path)
            VALUES (
                :id, :title, '', :cat,
                ARRAY[:cat]::text[],
                to_tsvector('english', :title || ' ' || :cat),
                ''
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": item_id, "title": title, "cat": cat},
    )


def _seed_embedding(session, item_id: str, emb: list[float]) -> None:
    from fitgraph.retrieval.pgvector_store import upsert_embeddings  # noqa: PLC0415

    upsert_embeddings(session, [(item_id, emb)], model_version="v1")


def _seed_user(session, email: str) -> int:
    """Insert a user and return its id."""
    from fitgraph.db.models import User  # noqa: PLC0415

    user = User(email=email)
    session.add(user)
    session.flush()
    return user.id


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------


class TestHealthz:
    def test_healthz_ok(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["model_version"] == "v1"

    def test_healthz_no_model(self, client_no_model):
        resp = client_no_model.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_version"] is None


# ---------------------------------------------------------------------------
# /catalog/search
# ---------------------------------------------------------------------------


class TestCatalogSearch:
    def test_search_returns_matching_items(self, client, db_session):
        _seed_item(db_session, "srch_001", "red linen shirt", "tops")
        _seed_item(db_session, "srch_002", "blue denim jeans", "bottoms")
        db_session.flush()

        resp = client.get("/catalog/search", params={"q": "shirt"})
        assert resp.status_code == 200
        data = resp.json()
        ids = [it["item_id"] for it in data["items"]]
        assert "srch_001" in ids

    def test_search_respects_limit(self, client, db_session):
        for i in range(10):
            _seed_item(db_session, f"lim_{i:03d}", "cotton sweater", "tops")
        db_session.flush()

        resp = client.get("/catalog/search", params={"q": "sweater", "limit": 3})
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 3

    def test_search_empty_for_unknown_query(self, client, db_session):
        resp = client.get("/catalog/search", params={"q": "xyzzy_notreal_42"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# /outfits POST + GET
# ---------------------------------------------------------------------------


class TestOutfits:
    def test_create_outfit(self, client, db_session):
        user_id = _seed_user(db_session, "outfit_create@example.com")
        _seed_item(db_session, "oi_001", "shirt", "tops")
        _seed_item(db_session, "oi_002", "trousers", "bottoms")
        db_session.flush()

        resp = client.post(
            "/outfits",
            json={"user_id": user_id, "name": "Daily Look", "item_ids": ["oi_001", "oi_002"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Daily Look"
        assert data["user_id"] == user_id
        assert set(data["item_ids"]) == {"oi_001", "oi_002"}

    def test_create_outfit_empty_items(self, client, db_session):
        user_id = _seed_user(db_session, "outfit_empty@example.com")
        db_session.flush()

        resp = client.post(
            "/outfits",
            json={"user_id": user_id, "name": "Empty", "item_ids": []},
        )
        assert resp.status_code == 201
        assert resp.json()["item_ids"] == []

    def test_get_outfits_empty(self, client):
        resp = client.get("/outfits", params={"user_id": 999999})
        assert resp.status_code == 200
        assert resp.json()["outfits"] == []

    def test_get_outfits_returns_created_outfit(self, client, db_session):
        user_id = _seed_user(db_session, "outfit_get@example.com")
        _seed_item(db_session, "go_001", "jacket", "tops")
        db_session.flush()

        # Create outfit via POST
        post_resp = client.post(
            "/outfits",
            json={"user_id": user_id, "name": "Weekend", "item_ids": ["go_001"]},
        )
        assert post_resp.status_code == 201

        # GET history
        get_resp = client.get("/outfits", params={"user_id": user_id})
        assert get_resp.status_code == 200
        outfits = get_resp.json()["outfits"]
        assert len(outfits) >= 1
        names = [o["outfit_name"] for o in outfits]
        assert "Weekend" in names


# ---------------------------------------------------------------------------
# /feedback
# ---------------------------------------------------------------------------


class TestFeedback:
    def test_feedback_ok(self, client, db_session):
        user_id = _seed_user(db_session, "feedback_ok@example.com")
        db_session.flush()

        resp = client.post(
            "/feedback",
            json={
                "user_id": user_id,
                "query_item_id": "q_001",
                "suggested_item_id": "s_001",
                "rating": 1,
            },
        )
        assert resp.status_code == 200
        # Phase 9: returns "queued" when Redis is up, "ok" when falling back to DB
        assert resp.json()["status"] in {"ok", "queued"}

    def test_feedback_negative_rating(self, client, db_session):
        user_id = _seed_user(db_session, "feedback_neg@example.com")
        db_session.flush()

        resp = client.post(
            "/feedback",
            json={
                "user_id": user_id,
                "query_item_id": "q_002",
                "suggested_item_id": "s_002",
                "rating": -1,
            },
        )
        assert resp.status_code == 200
        # Phase 9: returns "queued" when Redis is up, "ok" when falling back to DB
        assert resp.json()["status"] in {"ok", "queued"}


# ---------------------------------------------------------------------------
# /compatibility
# ---------------------------------------------------------------------------


class TestCompatibility:
    def test_compatibility_returns_score(self, client, db_session):
        emb = _random_emb()
        _seed_item(db_session, "compat_a", "shirt", "tops")
        _seed_item(db_session, "compat_b", "trousers", "bottoms")
        _seed_embedding(db_session, "compat_a", emb)
        _seed_embedding(db_session, "compat_b", emb)
        db_session.flush()

        resp = client.post(
            "/compatibility",
            json={"item_id_a": "compat_a", "item_id_b": "compat_b"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert -1.0 <= data["score"] <= 1.0

    def test_compatibility_missing_item_404(self, client):
        resp = client.post(
            "/compatibility",
            json={"item_id_a": "does_not_exist_a", "item_id_b": "does_not_exist_b"},
        )
        assert resp.status_code == 404

    def test_compatibility_no_model_503(self, client_no_model, db_session):
        emb = _random_emb()
        _seed_item(db_session, "compat_nm_a", "shirt", "tops")
        _seed_item(db_session, "compat_nm_b", "trousers", "bottoms")
        _seed_embedding(db_session, "compat_nm_a", emb)
        _seed_embedding(db_session, "compat_nm_b", emb)
        db_session.flush()

        # The client_no_model fixture does NOT override the DB — re-create with db
        app = create_app()
        from fastapi.testclient import TestClient  # noqa: PLC0415

        from fitgraph.api.routes import _get_db, _get_svc  # noqa: PLC0415

        app.dependency_overrides[_get_db] = lambda: (yield db_session)
        app.dependency_overrides[_get_svc] = lambda: ModelService()

        with TestClient(app) as c:
            resp = c.post(
                "/compatibility",
                json={"item_id_a": "compat_nm_a", "item_id_b": "compat_nm_b"},
            )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# /suggest
# ---------------------------------------------------------------------------


class TestSuggest:
    def test_suggest_returns_schema(self, client, db_session):
        """POST /suggest with a generated test image returns correct schema."""
        emb = _random_emb()
        _seed_item(db_session, "sug_001", "silk blouse", "tops")
        _seed_item(db_session, "sug_002", "denim shorts", "bottoms")
        _seed_embedding(db_session, "sug_001", emb)
        _seed_embedding(db_session, "sug_002", emb)
        db_session.flush()

        img_bytes = _make_image_bytes()
        resp = client.post(
            "/suggest",
            data={"text": "blue shirt", "category": "tops", "k": "2"},
            files={"image": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert "query" in data
        # Each suggestion should have the required keys
        for s in data["suggestions"]:
            assert "item_id" in s
            assert "score" in s
            assert "title" in s
            assert "semantic_category" in s
            assert "image_path" in s

    def test_suggest_no_model_503(self, db_session):
        """Returns 503 when no model is loaded."""
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app = create_app()
        from fitgraph.api.routes import _get_db, _get_svc  # noqa: PLC0415

        def _override_db():
            yield db_session

        app.dependency_overrides[_get_db] = _override_db
        app.dependency_overrides[_get_svc] = lambda: ModelService()

        img_bytes = _make_image_bytes()
        with TestClient(app) as c:
            resp = c.post(
                "/suggest",
                data={"text": "", "k": "5"},
                files={"image": ("t.jpg", img_bytes, "image/jpeg")},
            )
        assert resp.status_code == 503
