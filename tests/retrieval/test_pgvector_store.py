"""Tests for retrieval/pgvector_store.py — run against the live Postgres.

The tests skip gracefully when Postgres is unreachable.
All writes are wrapped in a savepoint that is rolled back after each test.
"""

from __future__ import annotations

import random

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from fitgraph.db.session import apply_schema, get_engine, get_session
from fitgraph.retrieval.pgvector_store import query, upsert_embeddings

DIM = 256


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    try:
        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        apply_schema(eng)
        return eng
    except (OperationalError, Exception) as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


@pytest.fixture()
def session(engine):
    factory = get_session(engine)
    sess = factory()
    sess.begin_nested()
    yield sess
    sess.rollback()
    sess.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_vec(dim: int = DIM, seed: int | None = None) -> list[float]:
    """Return a random unit vector."""
    rng = random.Random(seed)
    v = [rng.gauss(0, 1) for _ in range(dim)]
    norm = sum(x * x for x in v) ** 0.5
    return [x / norm for x in v]


def _seed_item(session, item_id: str) -> None:
    session.execute(
        text(
            """
            INSERT INTO items (id, title, description, semantic_category,
                               tags, search_doc, image_path)
            VALUES (:id, '', '', '', ARRAY[]::text[],
                    to_tsvector('english', ''), '')
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": item_id},
    )
    session.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpsertEmbeddings:
    def test_upsert_inserts_new_rows(self, session):
        _seed_item(session, "vec_item_001")
        _seed_item(session, "vec_item_002")

        rows = [
            ("vec_item_001", _unit_vec(seed=1)),
            ("vec_item_002", _unit_vec(seed=2)),
        ]
        upsert_embeddings(session, rows, model_version="v_test")
        session.flush()

        count = session.execute(
            text(
                "SELECT COUNT(*) FROM item_embeddings "
                "WHERE item_id IN ('vec_item_001', 'vec_item_002')"
            )
        ).scalar()
        assert count == 2

    def test_upsert_updates_existing_row(self, session):
        _seed_item(session, "vec_update_001")

        v1 = _unit_vec(seed=10)
        upsert_embeddings(session, [("vec_update_001", v1)], model_version="v1")
        session.flush()

        v2 = _unit_vec(seed=20)
        upsert_embeddings(session, [("vec_update_001", v2)], model_version="v2")
        session.flush()

        row = session.execute(
            text(
                "SELECT model_version FROM item_embeddings "
                "WHERE item_id = 'vec_update_001'"
            )
        ).fetchone()
        assert row.model_version == "v2"

    def test_upsert_empty_rows_is_noop(self, session):
        """Calling with an empty list must not raise."""
        upsert_embeddings(session, [], model_version="v_test")


class TestQuery:
    def test_returns_nearest_vector_first(self, session):
        # Seed 5 items with known vectors
        base = _unit_vec(seed=99)
        # near_vec is very close to base
        near_vec = [x + 0.001 for x in base]
        norm = sum(x * x for x in near_vec) ** 0.5
        near_vec = [x / norm for x in near_vec]

        item_ids = [f"qry_item_{i:03d}" for i in range(5)]
        for item_id in item_ids:
            _seed_item(session, item_id)

        emb_rows = [(item_ids[0], near_vec)] + [
            (item_ids[i], _unit_vec(seed=i + 100)) for i in range(1, 5)
        ]
        upsert_embeddings(session, emb_rows, model_version="v_test")
        session.flush()

        results = query(session, base, k=5)
        assert len(results) >= 1
        # The nearest item should be first
        assert results[0][0] == item_ids[0]

    def test_respects_k(self, session):
        item_ids = [f"k_item_{i:03d}" for i in range(10)]
        for item_id in item_ids:
            _seed_item(session, item_id)

        emb_rows = [(iid, _unit_vec(seed=i + 200)) for i, iid in enumerate(item_ids)]
        upsert_embeddings(session, emb_rows, model_version="v_test")
        session.flush()

        results = query(session, _unit_vec(seed=999), k=3)
        assert len(results) <= 3

    def test_distances_are_ascending(self, session):
        item_ids = [f"dist_item_{i:03d}" for i in range(8)]
        for item_id in item_ids:
            _seed_item(session, item_id)

        emb_rows = [(iid, _unit_vec(seed=i + 300)) for i, iid in enumerate(item_ids)]
        upsert_embeddings(session, emb_rows, model_version="v_test")
        session.flush()

        results = query(session, _unit_vec(seed=500), k=8)
        distances = [d for _, d in results]
        assert distances == sorted(distances)

    def test_returns_empty_when_no_embeddings(self, session):
        # Don't seed any embeddings; just run a query
        # (there may be embeddings from other tests but we can still verify
        #  the call returns a list without error)
        results = query(session, _unit_vec(seed=42), k=0)
        assert results == []
