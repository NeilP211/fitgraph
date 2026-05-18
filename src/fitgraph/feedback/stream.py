"""Redis Streams interface for FitGraph rating feedback.

Constants
---------
FEEDBACK_STREAM : str
    The Redis stream key that receives rating events.
FEEDBACK_GROUP : str
    The consumer-group name used by retrain workers.

Functions
---------
get_redis()
    Build a redis.Redis client from ``settings.redis_url``.
publish_rating(redis_client, event)
    XADD a rating event dict to the stream; return the message id.
ensure_group(redis_client)
    Create the consumer group if it doesn't already exist (idempotent).
consume_batch(redis_client, session, count, consumer)
    Read pending+new messages, persist each as a Rating row, XACK, return count.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import redis as redis_lib
from sqlalchemy.orm import Session

from fitgraph.config import settings
from fitgraph.db.models import Rating

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

FEEDBACK_STREAM: str = "fitgraph:feedback"
FEEDBACK_GROUP: str = "fitgraph:retrainers"

# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def get_redis() -> redis_lib.Redis:  # type: ignore[type-arg]
    """Return a redis.Redis client configured from ``settings.redis_url``."""
    return redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


def publish_rating(
    redis_client: redis_lib.Redis,  # type: ignore[type-arg]
    event: dict,
    stream: str = FEEDBACK_STREAM,
) -> str:
    """Append a rating event to the feedback stream.

    Parameters
    ----------
    redis_client:
        An open redis client (``decode_responses=True`` assumed).
    event:
        Dict with keys: ``user_id``, ``query_item_id``, ``suggested_item_id``,
        ``rating``, ``model_version``, ``created_at``.  All values are
        stringified before being written to the stream.
    stream:
        Redis stream key (defaults to ``FEEDBACK_STREAM``).  Override in tests
        for isolation.

    Returns
    -------
    str
        The Redis message id (e.g. ``"1234567890123-0"``).
    """
    fields = {k: "" if v is None else str(v) for k, v in event.items()}
    msg_id: str = redis_client.xadd(stream, fields)  # type: ignore[assignment]
    return msg_id


# ---------------------------------------------------------------------------
# Consumer group management
# ---------------------------------------------------------------------------


def ensure_group(redis_client: redis_lib.Redis, stream: str = FEEDBACK_STREAM) -> None:  # type: ignore[type-arg]
    """Create the consumer group on *stream* if it does not already exist.

    Uses ``XGROUP CREATE … $ MKSTREAM`` so the stream is also created if
    needed.  Swallows the ``BUSYGROUP`` error so the call is idempotent.
    """
    try:
        redis_client.xgroup_create(stream, FEEDBACK_GROUP, id="0", mkstream=True)
    except redis_lib.exceptions.ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            pass  # group already exists — fine
        else:
            raise


# ---------------------------------------------------------------------------
# Consume
# ---------------------------------------------------------------------------


def _parse_rating(fields: dict[str, Any]) -> Rating | None:
    """Convert stream message fields into a Rating ORM object.

    Returns ``None`` if required fields are missing or unparseable, so that
    callers can skip malformed messages without crashing.
    """
    try:
        user_id_raw = fields.get("user_id", "")
        user_id = int(user_id_raw) if user_id_raw else None

        query_item_id = fields.get("query_item_id") or None
        suggested_item_id = fields.get("suggested_item_id") or None

        rating_raw = fields.get("rating", "")
        rating = int(rating_raw) if rating_raw else None

        model_version = fields.get("model_version") or None

        created_at_raw = fields.get("created_at", "")
        if created_at_raw:
            try:
                created_at: datetime | None = datetime.fromisoformat(created_at_raw)
            except ValueError:
                created_at = datetime.now(UTC)
        else:
            created_at = datetime.now(UTC)

        return Rating(
            user_id=user_id,
            query_item_id=query_item_id,
            suggested_item_id=suggested_item_id,
            rating=rating,
            model_version=model_version,
            created_at=created_at,
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Malformed stream message, skipping: %s — %s", fields, exc)
        return None


def consume_batch(
    redis_client: redis_lib.Redis,  # type: ignore[type-arg]
    session: Session,
    count: int = 100,
    consumer: str = "worker-1",
    stream: str = FEEDBACK_STREAM,
) -> int:
    """Read up to *count* messages from the stream, persist them, and ACK.

    Reads first from the consumer's pending-entry list (PEL — messages
    delivered but not yet acknowledged), then from new messages (``>``).

    Parameters
    ----------
    redis_client:
        Open Redis client.
    session:
        SQLAlchemy session; caller is responsible for committing/rolling back.
    count:
        Maximum number of messages to consume per call.
    consumer:
        Consumer name within the group.
    stream:
        Stream key (defaults to ``FEEDBACK_STREAM``).

    Returns
    -------
    int
        Number of messages successfully processed (including skipped-malformed
        ones that were ACKed to prevent replay loops).
    """
    ensure_group(redis_client, stream)

    total = 0

    # 1. First drain the PEL (messages delivered to this consumer but not ACKed)
    pending_msgs = redis_client.xreadgroup(
        FEEDBACK_GROUP,
        consumer,
        {stream: "0"},  # "0" = start of PEL
        count=count,
    )
    total += _process_messages(redis_client, session, pending_msgs, stream)

    remaining = count - total
    if remaining <= 0:
        return total

    # 2. Then read new messages
    new_msgs = redis_client.xreadgroup(
        FEEDBACK_GROUP,
        consumer,
        {stream: ">"},  # ">" = only new, undelivered messages
        count=remaining,
    )
    total += _process_messages(redis_client, session, new_msgs, stream)

    return total


def _process_messages(
    redis_client: redis_lib.Redis,  # type: ignore[type-arg]
    session: Session,
    raw: list,
    stream: str,
) -> int:
    """Insert Rating rows for *raw* XREADGROUP results and XACK each one.

    Malformed messages are still ACKed (to prevent infinite replay) but their
    parse failures are logged.  Returns the number of messages processed.
    """
    processed = 0
    for _stream_name, messages in raw or []:
        for msg_id, fields in messages:
            rating_obj = _parse_rating(fields)
            if rating_obj is not None:
                try:
                    session.add(rating_obj)
                    session.flush()
                except Exception as exc:
                    logger.warning("Failed to persist rating from message %s: %s", msg_id, exc)
                    session.rollback()
            redis_client.xack(stream, FEEDBACK_GROUP, msg_id)
            processed += 1
    return processed
