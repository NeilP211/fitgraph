"""Tests for fitgraph.feedback.stream.

Runs against a live Redis + Postgres instance; skips gracefully if either is
unreachable.  Each test uses a unique stream key so parallel runs don't
interfere with each other.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from fitgraph.db.models import Rating

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def redis_client():
    """Return a Redis client; skip the module if Redis is unavailable."""
    try:
        from fitgraph.feedback.stream import get_redis  # noqa: PLC0415

        client = get_redis()
        client.ping()
        return client
    except Exception as exc:
        pytest.skip(f"Redis unavailable: {exc}")


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
def db_session(engine):
    """Session that rolls back after each test."""
    from fitgraph.db.session import get_session  # noqa: PLC0415

    factory = get_session(engine)
    sess = factory()
    sess.begin_nested()
    yield sess
    sess.rollback()
    sess.close()


def _unique_stream() -> str:
    """Return a unique Redis stream key for test isolation."""
    return f"fitgraph:feedback:test:{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(**kwargs) -> dict:
    """Build a minimal rating event dict."""
    defaults = {
        "user_id": 1,
        "query_item_id": "item_q",
        "suggested_item_id": "item_s",
        "rating": 1,
        "model_version": "v1",
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPublishRating:
    def test_publish_returns_message_id(self, redis_client):
        """publish_rating returns a non-empty message id string."""
        from fitgraph.feedback.stream import publish_rating  # noqa: PLC0415

        stream = _unique_stream()
        msg_id = publish_rating(redis_client, _make_event(), stream=stream)
        assert isinstance(msg_id, str)
        assert "-" in msg_id  # Redis stream id format: "<ms>-<seq>"

        # Cleanup
        redis_client.delete(stream)

    def test_publish_event_is_in_stream(self, redis_client):
        """After publishing, the message appears in the stream."""
        from fitgraph.feedback.stream import publish_rating  # noqa: PLC0415

        stream = _unique_stream()
        publish_rating(redis_client, _make_event(query_item_id="chk_q"), stream=stream)

        messages = redis_client.xrange(stream)
        assert len(messages) == 1
        fields = messages[0][1]
        assert fields["query_item_id"] == "chk_q"

        redis_client.delete(stream)


class TestEnsureGroup:
    def test_ensure_group_is_idempotent(self, redis_client):
        """Calling ensure_group twice raises no error."""
        from fitgraph.feedback.stream import ensure_group  # noqa: PLC0415

        stream = _unique_stream()
        ensure_group(redis_client, stream=stream)
        ensure_group(redis_client, stream=stream)  # must not raise

        redis_client.delete(stream)


class TestConsumeBatch:
    def test_consume_batch_round_trip(self, redis_client, db_session):
        """publish_rating then consume_batch lands the rating in Postgres."""
        from fitgraph.feedback.stream import (  # noqa: PLC0415
            consume_batch,
            publish_rating,
        )

        stream = _unique_stream()
        event = _make_event(
            user_id=None,
            query_item_id="rt_q",
            suggested_item_id="rt_s",
            rating=1,
        )
        publish_rating(redis_client, event, stream=stream)

        n = consume_batch(redis_client, db_session, count=10, stream=stream)
        db_session.flush()

        assert n == 1

        rating = (
            db_session.query(Rating)
            .filter(
                Rating.query_item_id == "rt_q",
                Rating.suggested_item_id == "rt_s",
            )
            .first()
        )
        assert rating is not None
        assert rating.rating == 1

        redis_client.delete(stream)

    def test_consume_batch_returns_correct_count(self, redis_client, db_session):
        """consume_batch returns the exact number of messages published."""
        from fitgraph.feedback.stream import (  # noqa: PLC0415
            consume_batch,
            publish_rating,
        )

        stream = _unique_stream()
        for i in range(3):
            publish_rating(redis_client, _make_event(suggested_item_id=f"cnt_{i}"), stream=stream)

        n = consume_batch(redis_client, db_session, count=10, stream=stream)
        assert n == 3

        redis_client.delete(stream)

    def test_consume_batch_empty_stream_returns_zero(self, redis_client, db_session):
        """consume_batch on an empty / fully-consumed stream returns 0."""
        from fitgraph.feedback.stream import (  # noqa: PLC0415
            consume_batch,
            ensure_group,
        )

        stream = _unique_stream()
        ensure_group(redis_client, stream=stream)

        n = consume_batch(redis_client, db_session, count=10, stream=stream)
        assert n == 0

        redis_client.delete(stream)

    def test_consume_batch_skips_malformed_message(self, redis_client, db_session):
        """A message with an unparseable rating field is skipped without crashing."""
        from fitgraph.feedback.stream import (  # noqa: PLC0415
            consume_batch,
            ensure_group,
        )

        stream = _unique_stream()
        ensure_group(redis_client, stream=stream)

        # Inject a malformed message directly (bad rating value)
        redis_client.xadd(
            stream,
            {
                "user_id": "not_an_int___",  # will cause int() to fail
                "query_item_id": "mal_q",
                "suggested_item_id": "mal_s",
                "rating": "not_a_number",
                "model_version": "v1",
                "created_at": "bad-date",
            },
        )

        # Should not raise; should still report 1 processed (acked even if skipped)
        n = consume_batch(redis_client, db_session, count=10, stream=stream)
        assert n == 1

        # No Rating row should have been inserted for this malformed message
        # (user_id "not_an_int___" can't be parsed)
        count = (
            db_session.query(Rating)
            .filter(Rating.query_item_id == "mal_q")
            .count()
        )
        assert count == 0

        redis_client.delete(stream)

    def test_consume_batch_does_not_double_consume(self, redis_client, db_session):
        """Messages are ACKed after consume; a second call returns 0."""
        from fitgraph.feedback.stream import (  # noqa: PLC0415
            consume_batch,
            publish_rating,
        )

        stream = _unique_stream()
        publish_rating(redis_client, _make_event(), stream=stream)

        first = consume_batch(redis_client, db_session, count=10, stream=stream)
        second = consume_batch(redis_client, db_session, count=10, stream=stream)

        assert first == 1
        assert second == 0

        redis_client.delete(stream)
