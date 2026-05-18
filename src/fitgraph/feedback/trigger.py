"""Retrain trigger logic for FitGraph active-learning loop.

Functions
---------
new_ratings_count(session)
    How many ratings have arrived since the current active model version.
should_retrain(session)
    Return True when the ratings count meets or exceeds ``settings.retrain_threshold``.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from fitgraph.config import settings
from fitgraph.db.models import ModelVersion
from fitgraph.db.queries import rating_volume_since

logger = logging.getLogger(__name__)


def _active_model_version(session: Session) -> ModelVersion | None:
    """Return the currently active ModelVersion, or fall back to the most recent.

    Look-up order:
    1. The row with ``is_active = True``.
    2. If none, the most recently created row (highest ``created_at``).
    3. If the table is empty, return ``None``.
    """
    active = (
        session.query(ModelVersion)
        .filter(ModelVersion.is_active.is_(True))
        .first()
    )
    if active is not None:
        return active

    # Fall back to the most recently created version
    return (
        session.query(ModelVersion)
        .order_by(ModelVersion.created_at.desc())
        .first()
    )


def new_ratings_count(session: Session) -> int:
    """Return the number of ratings collected since the active model version.

    Returns 0 when no model version exists yet.
    """
    mv = _active_model_version(session)
    if mv is None:
        logger.debug("No model version found; returning 0 for new_ratings_count")
        return 0
    count = rating_volume_since(session, mv.version)
    logger.debug("new_ratings_count: version=%s count=%d", mv.version, count)
    return count


def should_retrain(session: Session) -> bool:
    """Return True when enough new ratings have accumulated to justify a retrain.

    Compares :func:`new_ratings_count` against ``settings.retrain_threshold``.
    """
    count = new_ratings_count(session)
    triggered = count >= settings.retrain_threshold
    logger.info(
        "should_retrain: count=%d threshold=%d triggered=%s",
        count,
        settings.retrain_threshold,
        triggered,
    )
    return triggered
