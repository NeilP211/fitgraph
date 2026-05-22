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
    list_categories,
    list_items_by_category,
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
        # Unique token so assertions hold whether or not the real catalog
        # has been seeded into the shared database.
        _seed_item(session, "tag_test_001", title="zqxuniqueknit pullover", cat="tops")
        _seed_item(session, "tag_test_002", title="silk blouse", cat="tops")
        _seed_item(session, "tag_test_003", title="denim jeans", cat="bottoms")

        results = search_items_by_tag(session, "zqxuniqueknit")
        ids = [item.id for item in results]
        assert "tag_test_001" in ids
        assert "tag_test_003" not in ids

    def test_ranks_best_match_first(self, session):
        # Unique token so ranking is deterministic regardless of seeded catalog.
        # The token appears in both title and category for _004 → higher rank.
        _seed_item(session, "rank_test_004", title="zqxrankterm coat", cat="zqxrankterm")
        _seed_item(session, "rank_test_005", title="zqxrankterm top", cat="tops")

        results = search_items_by_tag(session, "zqxrankterm")
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


# ---------------------------------------------------------------------------
# list_categories
# ---------------------------------------------------------------------------


class TestListCategories:
    def test_returns_categories_with_counts(self, session):
        _seed_item(session, "cat_a1", title="x", cat="zqxcat_tops")
        _seed_item(session, "cat_a2", title="y", cat="zqxcat_tops")
        _seed_item(session, "cat_b1", title="z", cat="zqxcat_shoes")
        session.flush()
        rows = list_categories(session)
        by_cat = {r["category"]: r["count"] for r in rows}
        assert by_cat["zqxcat_tops"] == 2
        assert by_cat["zqxcat_shoes"] == 1

    def test_ordered_by_count_desc(self, session):
        _seed_item(session, "cat_ord_a1", title="a", cat="zqxcat_ord_big")
        _seed_item(session, "cat_ord_a2", title="b", cat="zqxcat_ord_big")
        _seed_item(session, "cat_ord_a3", title="c", cat="zqxcat_ord_big")
        _seed_item(session, "cat_ord_b1", title="d", cat="zqxcat_ord_small")
        session.flush()
        rows = list_categories(session)
        # Find positions of our test categories
        cats = [r["category"] for r in rows]
        idx_big = cats.index("zqxcat_ord_big")
        idx_small = cats.index("zqxcat_ord_small")
        assert idx_big < idx_small  # big count appears before small


# ---------------------------------------------------------------------------
# list_items_by_category
# ---------------------------------------------------------------------------


class TestListItemsByCategory:
    def test_paginates_within_category(self, session):
        for i in range(5):
            _seed_item(session, f"lic_{i}", title=f"item{i}", cat="zqxcat_bottoms")
        _seed_item(session, "lic_other", title="other", cat="zqxcat_hats")
        session.flush()
        page = list_items_by_category(session, "zqxcat_bottoms", limit=2, offset=0)
        assert len(page) == 2
        assert all(it.semantic_category == "zqxcat_bottoms" for it in page)
        page2 = list_items_by_category(session, "zqxcat_bottoms", limit=2, offset=2)
        assert len(page2) == 2
        assert {it.id for it in page} & {it.id for it in page2} == set()

    def test_filters_by_category(self, session):
        _seed_item(session, "licat_a1", title="top", cat="zqxcat_licat_tops")
        _seed_item(session, "licat_b1", title="shoe", cat="zqxcat_licat_shoes")
        session.flush()
        result = list_items_by_category(session, "zqxcat_licat_tops")
        ids = [it.id for it in result]
        assert "licat_a1" in ids
        assert "licat_b1" not in ids

    def test_returns_empty_for_unknown_category(self, session):
        result = list_items_by_category(session, "zqxcat_nonexistent_xyz")
        assert result == []
