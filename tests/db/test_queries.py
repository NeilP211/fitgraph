"""Tests for db/queries.py — run against the live Postgres.

The tests skip gracefully when Postgres is unreachable.
All writes are wrapped in a transaction that is rolled back after each test,
so the live database is left clean.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from fitgraph.db.models import Item, ModelVersion, Outfit, OutfitItem, Rating, User
from fitgraph.db.queries import (
    rating_volume_since,
    search_items_by_tag,
    user_outfit_history,
)
from fitgraph.db.session import apply_schema, get_engine, get_session

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """Attempt to connect to Postgres; skip the whole module if unreachable."""
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
    """Provide a session that rolls back all changes after each test."""
    factory = get_session(engine)
    sess = factory()
    sess.begin_nested()  # SAVEPOINT so we can roll back to here
    yield sess
    sess.rollback()
    sess.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_item(session, item_id: str, title: str = "", cat: str = "") -> Item:
    """Insert a minimal Item and refresh its search_doc via SQL."""
    session.execute(
        text(
            """
            INSERT INTO items (id, title, description, semantic_category,
                               tags, search_doc, image_path)
            VALUES (
                :id, :title, :descr, :cat,
                ARRAY[:cat]::text[],
                to_tsvector('english', :title || ' ' || :descr || ' ' || :cat),
                ''
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": item_id, "title": title, "descr": "", "cat": cat},
    )
    session.flush()
    return session.get(Item, item_id)


# ---------------------------------------------------------------------------
# Schema idempotency
# ---------------------------------------------------------------------------


class TestSchemaIdempotency:
    def test_apply_schema_twice(self, engine):
        """Calling apply_schema twice must not raise."""
        apply_schema(engine)
        apply_schema(engine)  # second call — must be a no-op


# ---------------------------------------------------------------------------
# search_items_by_tag
# ---------------------------------------------------------------------------


class TestSearchItemsByTag:
    def test_returns_matching_items(self, session):
        _seed_item(session, "tag_test_001", title="wool sweater", cat="tops")
        _seed_item(session, "tag_test_002", title="silk blouse", cat="tops")
        _seed_item(session, "tag_test_003", title="denim jeans", cat="bottoms")

        results = search_items_by_tag(session, "sweater")
        ids = [item.id for item in results]
        assert "tag_test_001" in ids
        assert "tag_test_003" not in ids

    def test_ranks_best_match_first(self, session):
        # 'jacket' appears in both title and category for _004 → higher rank
        _seed_item(session, "rank_test_004", title="leather jacket", cat="jacket")
        _seed_item(session, "rank_test_005", title="casual top", cat="jacket")

        results = search_items_by_tag(session, "jacket")
        assert len(results) >= 2
        # _004 should be ranked higher (title + category both match)
        assert results[0].id == "rank_test_004"

    def test_respects_limit(self, session):
        for i in range(10):
            _seed_item(session, f"lim_test_{i:03d}", title="shirt", cat="tops")
        results = search_items_by_tag(session, "shirt", limit=3)
        assert len(results) <= 3

    def test_no_results_for_unknown_query(self, session):
        results = search_items_by_tag(session, "xyzzy_nonexistent_token_42")
        assert results == []


# ---------------------------------------------------------------------------
# user_outfit_history
# ---------------------------------------------------------------------------


class TestUserOutfitHistory:
    def test_returns_outfits_with_items(self, session):
        # Seed user
        user = User(email="history_test@example.com")
        session.add(user)
        session.flush()

        # Seed items
        item_a = _seed_item(session, "hist_item_001", title="top", cat="tops")
        item_b = _seed_item(session, "hist_item_002", title="skirt", cat="bottoms")

        # Seed outfit
        outfit = Outfit(user_id=user.id, name="Test Outfit")
        session.add(outfit)
        session.flush()

        session.add(OutfitItem(outfit_id=outfit.id, item_id=item_a.id, position=0))
        session.add(OutfitItem(outfit_id=outfit.id, item_id=item_b.id, position=1))
        session.flush()

        history = user_outfit_history(session, user.id)

        assert len(history) == 1
        result = history[0]
        assert result["outfit_id"] == outfit.id
        assert result["outfit_name"] == "Test Outfit"
        item_ids = [it.id for it in result["items"]]
        assert "hist_item_001" in item_ids
        assert "hist_item_002" in item_ids

    def test_items_ordered_by_position(self, session):
        user = User(email="order_test@example.com")
        session.add(user)
        session.flush()

        items = [
            _seed_item(session, f"ord_item_{i:03d}", title=f"item {i}")
            for i in range(3)
        ]
        outfit = Outfit(user_id=user.id, name="Ordered")
        session.add(outfit)
        session.flush()

        # Insert in reverse order to confirm position sorting works
        for pos, item in reversed(list(enumerate(items))):
            session.add(OutfitItem(outfit_id=outfit.id, item_id=item.id, position=pos))
        session.flush()

        history = user_outfit_history(session, user.id)
        returned_ids = [it.id for it in history[0]["items"]]
        expected_ids = [f"ord_item_{i:03d}" for i in range(3)]
        assert returned_ids == expected_ids

    def test_empty_for_unknown_user(self, session):
        assert user_outfit_history(session, user_id=999999) == []


# ---------------------------------------------------------------------------
# rating_volume_since
# ---------------------------------------------------------------------------


class TestRatingVolumeSince:
    def test_counts_only_post_version_ratings(self, session):
        # Create model version with a timestamp in the past
        past = datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC)
        mv = ModelVersion(version="v_count_test", is_active=False, created_at=past)
        session.add(mv)
        session.flush()

        # One rating BEFORE the version timestamp (should not count)
        before = Rating(
            query_item_id="x",
            suggested_item_id="y",
            rating=1,
            created_at=datetime.datetime(1999, 6, 1, tzinfo=datetime.UTC),
        )
        # Two ratings AFTER the version timestamp (should count)
        after1 = Rating(
            query_item_id="x",
            suggested_item_id="y",
            rating=1,
            created_at=datetime.datetime(2000, 6, 1, tzinfo=datetime.UTC),
        )
        after2 = Rating(
            query_item_id="x",
            suggested_item_id="z",
            rating=-1,
            created_at=datetime.datetime(2001, 1, 1, tzinfo=datetime.UTC),
        )
        session.add_all([before, after1, after2])
        session.flush()

        count = rating_volume_since(session, "v_count_test")
        assert count == 2

    def test_returns_zero_for_unknown_version(self, session):
        assert rating_volume_since(session, "no_such_version") == 0
