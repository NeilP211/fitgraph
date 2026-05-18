"""SQLAlchemy engine + session factory, and schema bootstrap."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from fitgraph.config import settings

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_engine(url: str | None = None) -> Engine:
    """Return a SQLAlchemy engine.

    Uses *url* if given, otherwise ``settings.database_url``.
    """
    return create_engine(url or settings.database_url, pool_pre_ping=True)


def get_session(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return a configured :class:`sessionmaker` bound to *engine*."""
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations.

    Usage::

        with session_scope() as session:
            session.add(...)
    """
    factory = get_session(engine)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def apply_schema(engine: Engine) -> None:
    """Execute ``schema.sql`` against *engine* (idempotent).

    The SQL file uses ``IF NOT EXISTS`` throughout, so this is safe to call
    on an already-initialised database.
    """
    sql = _SCHEMA_PATH.read_text()
    with engine.begin() as conn:
        conn.execute(text(sql))
