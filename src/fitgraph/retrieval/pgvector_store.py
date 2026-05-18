"""pgvector-backed embedding store: upsert and ANN query."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_embeddings(
    session: Session,
    rows: list[tuple[str, list[float]]],
    model_version: str,
) -> None:
    """Upsert (item_id, embedding) pairs into ``item_embeddings``.

    Uses ``ON CONFLICT (item_id) DO UPDATE`` so repeated calls are safe.
    The *model_version* is stored alongside each embedding.

    Parameters
    ----------
    session:
        An active SQLAlchemy :class:`~sqlalchemy.orm.Session`.
    rows:
        List of ``(item_id, embedding_vector)`` tuples. The embedding must
        have 256 dimensions to match the ``vector(256)`` column.
    model_version:
        The model version string to tag each embedding with.
    """
    if not rows:
        return

    stmt = text(
        """
        INSERT INTO item_embeddings (item_id, embedding, model_version)
        VALUES (:item_id, CAST(:embedding AS vector(256)), :model_version)
        ON CONFLICT (item_id) DO UPDATE
            SET embedding      = EXCLUDED.embedding,
                model_version  = EXCLUDED.model_version
        """
    )
    for item_id, vec in rows:
        session.execute(
            stmt,
            {
                "item_id": item_id,
                "embedding": str(vec),  # pgvector accepts '[0.1, 0.2, ...]'
                "model_version": model_version,
            },
        )


def query(
    session: Session,
    vector: list[float],
    k: int = 20,
) -> list[tuple[str, float]]:
    """Approximate nearest-neighbour search using cosine distance.

    Parameters
    ----------
    session:
        An active SQLAlchemy :class:`~sqlalchemy.orm.Session`.
    vector:
        Query embedding (256-dim list of floats).
    k:
        Maximum number of results.

    Returns
    -------
    list[tuple[str, float]]
        ``(item_id, cosine_distance)`` pairs sorted ascending by distance
        (closest first).  Distance is in ``[0, 2]``; 0 means identical.
    """
    stmt = text(
        """
        SELECT item_id,
               embedding <=> CAST(:vec AS vector(256)) AS cosine_dist
        FROM   item_embeddings
        ORDER BY cosine_dist
        LIMIT  :k
        """
    )
    rows = session.execute(stmt, {"vec": str(vector), "k": k}).fetchall()
    return [(row.item_id, float(row.cosine_dist)) for row in rows]
