"""Tests for fitgraph.feedback.trigger.

Runs against a live Postgres instance; skips gracefully if unavailable.
All writes are wrapped in a savepoint that is rolled back after each test.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from fitgraph.db.models import ModelVersion, Rating

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """Return a SQLAlchemy engine; skip the module if Postgres is unavailable."""
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
def session(engine):
    """Session that rolls back all changes after each test."""
    from fitgraph.db.session import get_session  # noqa: PLC0415

    factory = get_session(engine)
    sess = factory()
    sess.begin_nested()
    yield sess
    sess.rollback()
    sess.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deactivate_all(session) -> None:
    """Mark every existing ModelVersion as inactive within this transaction.

    This ensures each test starts from a clean slate of 'no active version'
    even if other tests or scripts have committed active rows to the DB.
    All changes are rolled back at the end of the test via the savepoint.
    """
    session.query(ModelVersion).update({"is_active": False})
    session.flush()


def _seed_model_version(
    session,
    version: str,
    *,
    is_active: bool = True,
    created_at: datetime.datetime | None = None,
) -> ModelVersion:
    """Insert a ModelVersion row and return it."""
    if created_at is None:
        created_at = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
    mv = ModelVersion(version=version, is_active=is_active, created_at=created_at)
    session.add(mv)
    session.flush()
    return mv


def _seed_ratings_after(
    session, n: int, model_created_at: datetime.datetime
) -> None:
    """Insert *n* Rating rows with created_at strictly after *model_created_at*."""
    base = model_created_at + datetime.timedelta(seconds=1)
    for i in range(n):
        session.add(
            Rating(
                query_item_id=f"trig_q_{i}",
                suggested_item_id=f"trig_s_{i}",
                rating=1,
                created_at=base + datetime.timedelta(seconds=i),
            )
        )
    session.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNewRatingsCount:
    def test_returns_zero_with_no_model_version(self, session):
        """new_ratings_count returns 0 when no ModelVersion row exists."""
        from fitgraph.feedback.trigger import new_ratings_count  # noqa: PLC0415

        _deactivate_all(session)
        # Delete all model versions so the 'no version' branch is hit
        session.query(ModelVersion).delete()
        session.flush()

        count = new_ratings_count(session)
        assert count == 0

    def test_counts_ratings_since_active_version(self, session):
        """new_ratings_count counts only ratings created after the active version."""
        from fitgraph.feedback.trigger import new_ratings_count  # noqa: PLC0415

        _deactivate_all(session)

        mv_time = datetime.datetime(2023, 6, 1, tzinfo=datetime.UTC)
        _seed_model_version(session, "trig_cnt_v1", is_active=True, created_at=mv_time)

        # 2 ratings BEFORE the model version (should not count)
        for i in range(2):
            session.add(
                Rating(
                    query_item_id=f"before_{i}",
                    suggested_item_id="s",
                    rating=1,
                    created_at=mv_time - datetime.timedelta(days=1),
                )
            )
        # 4 ratings AFTER
        _seed_ratings_after(session, 4, mv_time)
        session.flush()

        count = new_ratings_count(session)
        assert count == 4


class TestShouldRetrain:
    def test_false_below_threshold(self, session):
        """should_retrain returns False when count < retrain_threshold."""
        from fitgraph.config import settings  # noqa: PLC0415
        from fitgraph.feedback.trigger import should_retrain  # noqa: PLC0415

        _deactivate_all(session)
        threshold = settings.retrain_threshold  # e.g. 100
        below = max(0, threshold - 1)

        mv_time = datetime.datetime(2022, 1, 1, tzinfo=datetime.UTC)
        _seed_model_version(session, "trig_false_v1", is_active=True, created_at=mv_time)
        _seed_ratings_after(session, below, mv_time)
        session.flush()

        assert should_retrain(session) is False

    def test_true_at_threshold(self, session):
        """should_retrain returns True when count == retrain_threshold."""
        from fitgraph.config import settings  # noqa: PLC0415
        from fitgraph.feedback.trigger import should_retrain  # noqa: PLC0415

        _deactivate_all(session)
        threshold = settings.retrain_threshold

        mv_time = datetime.datetime(2021, 1, 1, tzinfo=datetime.UTC)
        _seed_model_version(session, "trig_true_v1", is_active=True, created_at=mv_time)
        _seed_ratings_after(session, threshold, mv_time)
        session.flush()

        assert should_retrain(session) is True

    def test_true_above_threshold(self, session):
        """should_retrain returns True when count > retrain_threshold."""
        from fitgraph.config import settings  # noqa: PLC0415
        from fitgraph.feedback.trigger import should_retrain  # noqa: PLC0415

        _deactivate_all(session)
        threshold = settings.retrain_threshold
        above = threshold + 5

        mv_time = datetime.datetime(2020, 6, 1, tzinfo=datetime.UTC)
        _seed_model_version(session, "trig_above_v1", is_active=True, created_at=mv_time)
        _seed_ratings_after(session, above, mv_time)
        session.flush()

        assert should_retrain(session) is True

    def test_falls_back_to_most_recent_when_no_active(self, session):
        """should_retrain uses the most recent version when none is marked active."""
        from fitgraph.config import settings  # noqa: PLC0415
        from fitgraph.feedback.trigger import should_retrain  # noqa: PLC0415

        # Remove all existing versions so we have full control
        session.query(ModelVersion).delete()
        session.flush()

        threshold = settings.retrain_threshold

        # Older inactive version
        old_time = datetime.datetime(2019, 1, 1, tzinfo=datetime.UTC)
        _seed_model_version(
            session, "trig_old_v1", is_active=False, created_at=old_time
        )

        # Newer inactive version (should be chosen as fallback)
        new_time = datetime.datetime(2023, 1, 1, tzinfo=datetime.UTC)
        _seed_model_version(
            session, "trig_new_v1", is_active=False, created_at=new_time
        )

        # Seed ratings after the NEWER version
        _seed_ratings_after(session, threshold, new_time)
        session.flush()

        assert should_retrain(session) is True

    def test_false_when_no_model_version_exists(self, session):
        """should_retrain returns False when there is no ModelVersion row at all."""
        from fitgraph.feedback.trigger import should_retrain  # noqa: PLC0415

        session.query(ModelVersion).delete()
        session.flush()

        result = should_retrain(session)
        assert result is False
