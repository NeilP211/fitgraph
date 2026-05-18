"""Active-learning retrain script for FitGraph.

Pipeline
--------
1. Connect to Redis, ensure the consumer group exists, and drain all pending /
   new stream messages into the ``ratings`` Postgres table (consume_batch loop).
2. If ``--drain-only``, stop here.
3. Check ``should_retrain(session)`` (unless ``--force``).  If the threshold
   hasn't been reached, print a message and exit 0.
4. Load item embeddings + Polyvore splits, inject rating-derived pairs as
   active-learning signal into the training outfits, run the Trainer, save the
   new model version, and register it in ``model_versions``.

Active-learning signal
----------------------
Ratings are loaded from the ``ratings`` table and converted to synthetic
:class:`~fitgraph.data.polyvore.Outfit` objects:

* Thumbs-up (``rating > 0``): a 2-item outfit ``[query_item_id,
  suggested_item_id]`` is appended to ``train_outfits``.  The co-occurrence
  map inside the Trainer will then treat these as positive pairs.

* Thumbs-down (``rating < 0``): the pair is added to the Trainer's internal
  co-occurrence map as a *negative* — specifically, we ensure neither item id
  appears in the other's co-occurrence set.  Because the Trainer builds its
  hard-negative pool by *excluding* co-worn items, removing a "false positive"
  from the co-occurrence set means that (query, suggested) pair can and will be
  surfaced as a hard negative during training.

  The implementation subclasses / monkey-patches the co-occurrence map *after*
  ``Trainer.__init__`` to keep the change minimal and non-invasive.

Usage
-----
    python scripts/retrain.py
    python scripts/retrain.py --epochs 5 --force
    python scripts/retrain.py --drain-only
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("retrain")

# ---------------------------------------------------------------------------
# Paths (same layout as scripts/train.py)
# ---------------------------------------------------------------------------

_POLYVORE_ROOT = Path("data/raw/polyvore-outfit-dataset/polyvore_outfits")
_TYPESPACES_P = _POLYVORE_ROOT / "disjoint" / "typespaces.p"
_ITEM_METADATA = _POLYVORE_ROOT / "polyvore_item_metadata.json"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Active-learning retrain for FitGraph")
    p.add_argument(
        "--epochs",
        type=int,
        default=5,
        help="Number of training epochs (default: 5, intentionally small for quick runs)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Skip the retrain-threshold check and retrain unconditionally",
    )
    p.add_argument(
        "--drain-only",
        action="store_true",
        help="Only flush pending Redis messages to Postgres; do not retrain",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_item_types() -> dict[str, str]:
    import json  # noqa: PLC0415

    raw = json.loads(_ITEM_METADATA.read_text())
    return {iid: (meta.get("semantic_category", "") or "") for iid, meta in raw.items()}


def _drain_stream(redis_client, session) -> int:
    """Consume until the stream is empty; return total messages processed."""
    from fitgraph.feedback.stream import consume_batch, ensure_group  # noqa: PLC0415

    ensure_group(redis_client)
    total = 0
    while True:
        n = consume_batch(redis_client, session)
        total += n
        if n == 0:
            break
    return total


def _build_active_learning_outfits(session) -> tuple[list, list]:
    """Return (positive_outfits, negative_pairs) derived from the ratings table.

    positive_outfits
        List of :class:`~fitgraph.data.polyvore.Outfit` objects for thumbs-up
        ratings (``rating > 0``).  Each synthetic outfit has two items.
    negative_pairs
        List of ``(query_item_id, suggested_item_id)`` tuples for thumbs-down
        ratings (``rating < 0``).  These are used to *remove* pairs from the
        Trainer's co-occurrence map so they can surface as hard negatives.
    """
    from fitgraph.data.polyvore import Outfit as PolyOutfit  # noqa: PLC0415
    from fitgraph.db.models import Rating  # noqa: PLC0415

    ratings = session.query(Rating).all()

    positive_outfits: list[PolyOutfit] = []
    negative_pairs: list[tuple[str, str]] = []

    for r in ratings:
        qid = r.query_item_id
        sid = r.suggested_item_id
        if not qid or not sid:
            continue
        if r.rating is not None and r.rating > 0:
            # Synthetic 2-item outfit — treated as a positive pair by the Trainer
            positive_outfits.append(PolyOutfit(id=f"al_{r.id}", item_ids=[qid, sid]))
        elif r.rating is not None and r.rating < 0:
            negative_pairs.append((qid, sid))

    logger.info(
        "Active-learning signal: %d positive pairs, %d hard-negative pairs",
        len(positive_outfits),
        len(negative_pairs),
    )
    return positive_outfits, negative_pairs


def _inject_hard_negatives(trainer, negative_pairs: list[tuple[str, str]]) -> None:
    """Remove thumbs-down pairs from the Trainer's co-occurrence map.

    The Trainer mines hard negatives by excluding co-worn (co-occurrence) items
    from the negative pool.  By removing a (query, suggested) pair that a user
    explicitly disliked, we ensure it *can* appear as a hard negative during
    subsequent training steps.

    This is a lightweight, non-invasive post-init hook — we mutate
    ``trainer._cooccur_ids`` in place.
    """
    removed = 0
    for qid, sid in negative_pairs:
        if qid in trainer._cooccur_ids:
            trainer._cooccur_ids[qid].discard(sid)
            removed += 1
        if sid in trainer._cooccur_ids:
            trainer._cooccur_ids[sid].discard(qid)
            removed += 1
    logger.info("Removed %d co-occurrence entries for hard-negative pairs", removed)


def _register_model_version(session, version_dir: Path, val_auc: float) -> None:
    """Insert the new ModelVersion row and deactivate the old active one."""
    from fitgraph.db.models import ModelVersion  # noqa: PLC0415

    now = datetime.now(UTC)

    # Deactivate all current active versions
    session.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).update(
        {"is_active": False}
    )

    new_mv = ModelVersion(
        version=version_dir.name,
        path=str(version_dir),
        val_auc=val_auc,
        is_active=True,
        created_at=now,
    )
    session.add(new_mv)
    session.flush()
    logger.info(
        "Registered new model version: %s (val_auc=%.4f)", version_dir.name, val_auc
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()

    # Lazy imports so the script loads fast for --drain-only
    from fitgraph.config import Settings  # noqa: PLC0415
    from fitgraph.config import settings as default_settings
    from fitgraph.db.session import apply_schema, get_engine, get_session  # noqa: PLC0415
    from fitgraph.feedback.stream import get_redis  # noqa: PLC0415
    from fitgraph.feedback.trigger import new_ratings_count, should_retrain  # noqa: PLC0415

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------
    engine = get_engine()
    apply_schema(engine)
    session_factory = get_session(engine)
    session = session_factory()

    try:
        redis_client = get_redis()
        redis_client.ping()
    except Exception as exc:
        logger.error("Redis unavailable: %s — aborting", exc)
        session.close()
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 1: Drain the feedback stream into Postgres
    # ------------------------------------------------------------------
    try:
        total_drained = _drain_stream(redis_client, session)
        session.commit()
        print(f"Drained {total_drained} feedback message(s) from Redis to Postgres.")
    except Exception as exc:
        session.rollback()
        logger.error("Error draining stream: %s", exc)
        session.close()
        sys.exit(1)

    if args.drain_only:
        print("--drain-only specified; stopping after drain.")
        session.close()
        sys.exit(0)

    # ------------------------------------------------------------------
    # Step 2: Check retrain threshold
    # ------------------------------------------------------------------
    if not args.force:
        count = new_ratings_count(session)
        print(
            f"New ratings since last model: {count} "
            f"(threshold: {default_settings.retrain_threshold})"
        )
        if not should_retrain(session):
            print(
                f"Threshold not yet reached ({count} < "
                f"{default_settings.retrain_threshold}). Exiting without retrain."
            )
            session.close()
            sys.exit(0)
        print("Retrain threshold reached — proceeding with active-learning retrain.")
    else:
        print("--force specified; skipping threshold check.")

    # ------------------------------------------------------------------
    # Step 3: Load data
    # ------------------------------------------------------------------
    settings = Settings(epochs=args.epochs)

    npz_path = settings.embeddings_dir / "items.npz"
    if not npz_path.exists():
        logger.error("Embeddings file not found: %s", npz_path)
        session.close()
        sys.exit(1)

    logger.info("Loading embeddings from %s", npz_path)
    npz = np.load(npz_path)
    npz_ids: list[str] = [str(x) for x in npz["ids"]]
    fused_np: np.ndarray = npz["fused"].astype(np.float32)
    clip_np: np.ndarray = npz["clip_emb"].astype(np.float32)
    fused_tensor = torch.from_numpy(fused_np)
    clip_tensor = torch.from_numpy(clip_np)
    logger.info("Embeddings: %d items, fused_dim=%d", len(npz_ids), fused_np.shape[1])

    from fitgraph.data.splits import load_splits  # noqa: PLC0415
    from fitgraph.models.type_aware import TypeSpaceIndex  # noqa: PLC0415
    from fitgraph.training.trainer import Trainer  # noqa: PLC0415

    subset = None if settings.use_full else settings.subset_outfits
    logger.info("Loading splits (subset=%s)...", subset)
    splits = load_splits(_POLYVORE_ROOT, subset_outfits=subset)
    train_outfits = splits["train"]
    valid_outfits = splits["valid"]
    logger.info(
        "Splits: train=%d, valid=%d", len(train_outfits), len(valid_outfits)
    )

    logger.info("Loading type system...")
    type_index = TypeSpaceIndex.from_file(_TYPESPACES_P)
    all_item_types = _load_item_types()
    item_types = {iid: all_item_types.get(iid, "") for iid in npz_ids}

    # ------------------------------------------------------------------
    # Step 4: Inject active-learning signal
    # ------------------------------------------------------------------
    al_positive_outfits, al_negative_pairs = _build_active_learning_outfits(session)

    # Augment train_outfits with positive rating-derived synthetic outfits
    augmented_train = list(train_outfits) + al_positive_outfits
    logger.info(
        "Augmented train outfits: %d (base=%d + al_pos=%d)",
        len(augmented_train),
        len(train_outfits),
        len(al_positive_outfits),
    )

    # ------------------------------------------------------------------
    # Step 5: Build and run Trainer
    # ------------------------------------------------------------------
    trainer = Trainer(
        fused_tensor=fused_tensor,
        clip_tensor=clip_tensor,
        all_ids=npz_ids,
        train_outfits=augmented_train,
        valid_outfits=valid_outfits,
        settings=settings,
        item_types=item_types,
        type_index=type_index,
    )

    # Inject hard negatives: remove thumbs-down pairs from co-occurrence map
    if al_negative_pairs:
        _inject_hard_negatives(trainer, al_negative_pairs)

    logger.info("Starting training (%d epochs)...", settings.epochs)
    results = trainer.fit()

    val_auc: float = results["best_val_auc"]
    version_dir = Path(results["version_dir"])
    print(f"\nTraining complete! Best val AUC: {val_auc:.4f}  version: {version_dir.name}")

    # ------------------------------------------------------------------
    # Step 6: Register new model version in Postgres
    # ------------------------------------------------------------------
    try:
        _register_model_version(session, version_dir, val_auc)
        session.commit()
        print(f"Registered model version '{version_dir.name}' as active in Postgres.")
    except Exception as exc:
        session.rollback()
        logger.error("Failed to register model version: %s", exc)
    finally:
        session.close()


if __name__ == "__main__":
    main()
