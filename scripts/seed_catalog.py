"""Seed the FitGraph catalog: load Polyvore metadata + embeddings into Postgres.

Usage examples
--------------
Seed from the latest model's catalog_embeddings.npz (default):

    python scripts/seed_catalog.py --model-version v1

Point at a specific .npz:

    python scripts/seed_catalog.py \
        --embeddings data/models/v1/catalog_embeddings.npz \
        --model-version v1 \
        --limit 500

The script is **idempotent**: repeated runs upsert rather than duplicate.

NOTE: Do NOT run this against the real model output while retraining is in
      progress.  Use --limit with a small synthetic npz for integration tests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import text

# Ensure src/ is on the path when run directly (e.g. `python scripts/...`)
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from fitgraph.config import settings  # noqa: E402
from fitgraph.db.session import apply_schema, get_engine, session_scope  # noqa: E402
from fitgraph.retrieval.pgvector_store import upsert_embeddings  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenize(text_val: str) -> list[str]:
    """Split a string into lowercase alphanumeric tokens."""
    return [t for t in re.split(r"[^a-zA-Z0-9]+", text_val.lower()) if t]


def _display_title(title: str, url_name: str, category: str) -> str:
    """Best available display name: title, else title-cased url_name, else category.

    ~70% of Polyvore items have an empty ``title`` but a populated ``url_name``
    slug (e.g. "sacai luck cable knit cardigan"); fall back to that before the
    bare category so the catalog reads like real products instead of "Untitled".
    """
    title = (title or "").strip()
    if title:
        return title
    url_name = (url_name or "").strip()
    if url_name:
        return url_name.title()
    return (category or "").strip().title()


def _latest_npz(models_dir: Path) -> Path:
    """Return the catalog_embeddings.npz in the most-recently modified subdir."""
    candidates = sorted(
        models_dir.glob("*/catalog_embeddings.npz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No catalog_embeddings.npz found under {models_dir}"
        )
    return candidates[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed FitGraph catalog in Postgres.")
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=None,
        help="Path to .npz with 'ids' and 'emb' arrays. "
        "Defaults to the latest catalog_embeddings.npz in data/models/.",
    )
    parser.add_argument(
        "--model-version",
        required=True,
        help="Model version string, e.g. 'v1'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only seed the first N items (for partial / test seeds).",
    )
    args = parser.parse_args()

    # ---- Resolve npz path ------------------------------------------------
    npz_path: Path = args.embeddings or _latest_npz(settings.models_dir)
    print(f"Loading embeddings from: {npz_path}")
    npz = np.load(npz_path, allow_pickle=True)
    ids: list[str] = list(npz["ids"])
    embs: np.ndarray = npz["emb"]

    if args.limit is not None:
        ids = ids[: args.limit]
        embs = embs[: args.limit]

    print(f"  {len(ids):,} embedding(s) loaded, dim={embs.shape[1]}")

    # ---- Load Polyvore item metadata -------------------------------------
    metadata_path = (
        settings.raw_dir
        / "polyvore-outfit-dataset"
        / "polyvore_outfits"
        / "polyvore_item_metadata.json"
    )
    images_dir = (
        settings.raw_dir
        / "polyvore-outfit-dataset"
        / "polyvore_outfits"
        / "images"
    )

    polyvore_items: dict = {}
    raw_meta: dict = {}
    if metadata_path.exists():
        from fitgraph.data.polyvore import load_item_metadata  # noqa: F811

        polyvore_items = load_item_metadata(metadata_path, images_dir)
        raw_meta = json.loads(metadata_path.read_text())
        print(f"  {len(polyvore_items):,} Polyvore metadata entries loaded")
    else:
        print(f"  WARNING: metadata not found at {metadata_path}; items will have empty metadata")

    # ---- Bootstrap schema -----------------------------------------------
    engine = get_engine()
    print("Applying schema …")
    apply_schema(engine)

    # ---- Upsert items + embeddings ---------------------------------------
    items_inserted = 0
    embeddings_upserted = 0
    embedding_rows: list[tuple[str, list[float]]] = []

    BATCH = 500

    with session_scope(engine) as session:
        for item_id, emb_vec in zip(ids, embs, strict=True):
            meta = polyvore_items.get(item_id)

            description = (meta.description if meta else "") or ""
            category = (meta.category if meta else "") or ""
            image_path = str(meta.image_path) if meta else ""
            raw = raw_meta.get(item_id, {})
            title = _display_title(raw.get("title", ""), raw.get("url_name", ""), category)

            # Build tags: category + tokenised url_name / item_id
            tags = list({category} | set(_tokenize(item_id))) if category else _tokenize(item_id)

            # Build search_doc via SQL so we get a proper tsvector
            session.execute(
                text(
                    """
                    INSERT INTO items
                        (id, title, description, semantic_category, tags,
                         search_doc, image_path)
                    VALUES (
                        :id, :title, :descr, :cat, :tags,
                        to_tsvector('english',
                            :title || ' ' || :descr || ' ' || :cat),
                        :img
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title             = EXCLUDED.title,
                        description       = EXCLUDED.description,
                        semantic_category = EXCLUDED.semantic_category,
                        tags              = EXCLUDED.tags,
                        search_doc        = EXCLUDED.search_doc,
                        image_path        = EXCLUDED.image_path
                    """
                ),
                {
                    "id": item_id,
                    "title": title,
                    "descr": description,
                    "cat": category,
                    "tags": tags,
                    "img": image_path,
                },
            )
            items_inserted += 1
            embedding_rows.append((item_id, emb_vec.tolist()))

            # Flush in batches
            if len(embedding_rows) >= BATCH:
                upsert_embeddings(session, embedding_rows, args.model_version)
                embeddings_upserted += len(embedding_rows)
                embedding_rows.clear()

        # Flush remainder
        if embedding_rows:
            upsert_embeddings(session, embedding_rows, args.model_version)
            embeddings_upserted += len(embedding_rows)

        # ---- Register / update model_versions row -----------------------
        session.execute(
            text(
                """
                INSERT INTO model_versions (version, is_active, created_at)
                VALUES (:version, true, now())
                ON CONFLICT (version) DO UPDATE SET
                    is_active  = true
                """
            ),
            {"version": args.model_version},
        )
        # Deactivate all other versions
        session.execute(
            text(
                """
                UPDATE model_versions
                SET    is_active = false
                WHERE  version <> :version
                """
            ),
            {"version": args.model_version},
        )

    print(
        f"\nDone.\n"
        f"  items upserted    : {items_inserted:,}\n"
        f"  embeddings upserted: {embeddings_upserted:,}\n"
        f"  model version     : {args.model_version} (active=true)\n"
    )


if __name__ == "__main__":
    main()
