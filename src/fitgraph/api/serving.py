"""Model serving: load checkpoints, embed images, score pairs, suggest items."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch

from fitgraph.config import settings
from fitgraph.models.hgat import HGAT
from fitgraph.models.type_aware import TypeAwareScorer, TypeSpaceIndex

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Checkpoint discovery
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^v(\d+)$")

_REQUIRED_FILES = {"model.pt", "meta.json", "type_index.json"}


def latest_model_dir() -> Path | None:
    """Return the highest ``v{N}`` directory under ``data/models/`` with a complete
    checkpoint (``model.pt``, ``meta.json``, ``type_index.json``).

    Returns ``None`` if no valid checkpoint directory exists.
    """
    models_root = settings.models_dir
    if not models_root.exists():
        return None

    best_n = -1
    best_dir: Path | None = None
    for candidate in models_root.iterdir():
        m = _VERSION_RE.match(candidate.name)
        if not m or not candidate.is_dir():
            continue
        n = int(m.group(1))
        if all((candidate / f).exists() for f in _REQUIRED_FILES):
            if n > best_n:
                best_n = n
                best_dir = candidate

    return best_dir


# ---------------------------------------------------------------------------
# ModelService
# ---------------------------------------------------------------------------


class ModelService:
    """Load and serve a FitGraph checkpoint.

    Usage::

        svc = ModelService()
        svc.load(Path("data/models/v1"))

        emb = svc.embed_image(Path("shirt.jpg"), "cotton shirt")
        score = svc.score(emb, "tops", other_emb, "bottoms")
    """

    def __init__(self) -> None:
        self._model: HGAT | None = None
        self._scorer: TypeAwareScorer | None = None
        self._type_index: TypeSpaceIndex | None = None
        self._item_types: dict[str, str] = {}
        self._version: str | None = None
        self._model_dir: Path | None = None

        # Lazy-loaded encoders (heavy; skip until needed)
        self._clip: object | None = None  # ClipEncoder
        self._text: object | None = None  # TextEncoder

        self._device = torch.device("cpu")

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, model_dir: Path) -> None:
        """Reconstruct the model from a checkpoint directory.

        Reads ``meta.json`` for hyperparameters, loads ``model.pt`` state dicts
        into :class:`~fitgraph.models.hgat.HGAT` and
        :class:`~fitgraph.models.type_aware.TypeAwareScorer`, and reads the
        ``item_id -> type`` map from ``type_index.json``.
        """
        meta_path = model_dir / "meta.json"
        meta = json.loads(meta_path.read_text())

        in_dim: int = meta.get("in_dim", 896)
        hidden_dim: int = meta.get("hidden_dim", 256)
        num_layers: int = meta.get("num_layers", 2)
        num_heads: int = meta.get("num_heads", 4)
        dropout: float = meta.get("dropout", 0.2)
        num_spaces: int = meta.get("num_spaces", 1)

        self._model = HGAT(
            in_dim=in_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            dropout=dropout,
        )
        self._scorer = TypeAwareScorer(num_spaces=num_spaces, dim=hidden_dim)

        ckpt = torch.load(
            model_dir / "model.pt",
            map_location=self._device,
            weights_only=True,
        )
        self._model.load_state_dict(ckpt["hgat"])
        self._scorer.load_state_dict(ckpt["scorer"])
        self._model.eval()
        self._scorer.eval()

        # Load type index + item->type map
        type_index_data = json.loads((model_dir / "type_index.json").read_text())
        self._type_index = TypeSpaceIndex.from_dict(type_index_data)
        self._item_types = type_index_data.get("item_types", {})

        self._version = meta.get("version", model_dir.name)
        self._model_dir = model_dir
        logger.info("Loaded model version %s from %s", self._version, model_dir)

    # ------------------------------------------------------------------
    # Lazy encoder access
    # ------------------------------------------------------------------

    def _get_clip(self):  # noqa: ANN202
        if self._clip is None:
            from fitgraph.embeddings.clip_encoder import ClipEncoder  # noqa: PLC0415

            self._clip = ClipEncoder()
        return self._clip

    def _get_text(self):  # noqa: ANN202
        if self._text is None:
            from fitgraph.embeddings.text_encoder import TextEncoder  # noqa: PLC0415

            self._text = TextEncoder()
        return self._text

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def embed_image(self, image_path: Path, text: str = "") -> np.ndarray:
        """Embed a single image (with optional text) to a 256-d L2-normalized vector.

        Uses the CLIP encoder for the image, the text encoder for the text
        description, fuses them, then runs :meth:`HGAT.embed_features`.

        Parameters
        ----------
        image_path:
            Path to a JPEG / PNG image file.
        text:
            Optional textual description of the item.

        Returns
        -------
        np.ndarray of shape ``(256,)``, dtype float32, L2-normalised.
        """
        if self._model is None:
            raise RuntimeError("ModelService has not been loaded. Call load() first.")

        from fitgraph.embeddings.fusion import fuse  # noqa: PLC0415

        # Encode image (512-d)
        clip_emb = self._get_clip().encode_images([image_path])  # (1, 512)

        # Encode text (384-d)
        text_str = text or ""
        txt_emb = self._get_text().encode([text_str])  # (1, 384)

        # Fuse -> (1, 896), L2-normalised
        fused = fuse(clip_emb, txt_emb)  # (1, 896)

        x = torch.from_numpy(fused).to(self._device)
        with torch.no_grad():
            emb = self._model.embed_features(x)  # (1, 256)
        return emb.squeeze(0).cpu().numpy().astype(np.float32)

    def score(
        self,
        emb_a: np.ndarray,
        type_a: str,
        emb_b: np.ndarray,
        type_b: str,
    ) -> float:
        """Type-aware compatibility score between two 256-d embeddings.

        Parameters
        ----------
        emb_a, emb_b:
            256-d L2-normalised embedding vectors.
        type_a, type_b:
            Semantic categories (e.g. ``"tops"``, ``"bottoms"``).

        Returns
        -------
        float in ``[-1, 1]``.
        """
        if self._scorer is None or self._type_index is None:
            raise RuntimeError("ModelService has not been loaded. Call load() first.")

        space_id = self._type_index.space_of(type_a, type_b)
        ta = torch.from_numpy(emb_a).unsqueeze(0).to(self._device)  # (1, 256)
        tb = torch.from_numpy(emb_b).unsqueeze(0).to(self._device)  # (1, 256)
        sid = torch.tensor([space_id], dtype=torch.long, device=self._device)
        with torch.no_grad():
            s = self._scorer.score_pairs(ta, tb, sid)
        return float(s.item())

    def suggest(
        self,
        query_emb: np.ndarray,
        query_type: str,
        session: Session,
        k: int = 12,
    ) -> list[dict]:
        """Suggest compatible items for a query embedding.

        Retrieves ``5*k`` nearest catalog items via pgvector ANN, then re-ranks
        them by type-aware compatibility score, returning the top ``k``.

        Parameters
        ----------
        query_emb:
            256-d query embedding (L2-normalised).
        query_type:
            Semantic category of the query item.
        session:
            Active SQLAlchemy session with pgvector access.
        k:
            Number of items to return.

        Returns
        -------
        List of dicts with keys ``item_id``, ``score``, ``title``,
        ``semantic_category``, ``image_path``.
        """
        if self._scorer is None or self._type_index is None:
            raise RuntimeError("ModelService has not been loaded. Call load() first.")

        from fitgraph.db.models import Item, ItemEmbedding  # noqa: PLC0415
        from fitgraph.retrieval.pgvector_store import query as pgvector_query  # noqa: PLC0415

        # ANN retrieval — fetch 5*k candidates
        candidates_raw = pgvector_query(session, query_emb.tolist(), k=5 * k)
        if not candidates_raw:
            return []

        # Fetch item metadata for candidates
        candidate_ids = [row[0] for row in candidates_raw]
        items_by_id: dict[str, Item] = {
            item.id: item
            for item in session.query(Item).filter(Item.id.in_(candidate_ids)).all()
        }
        embs_by_id: dict[str, np.ndarray] = {}
        for ie in (
            session.query(ItemEmbedding)
            .filter(ItemEmbedding.item_id.in_(candidate_ids))
            .all()
        ):
            if ie.embedding is not None:
                embs_by_id[ie.item_id] = np.array(ie.embedding, dtype=np.float32)

        # Re-rank by type-aware score
        scored: list[tuple[float, str]] = []
        for item_id, _dist in candidates_raw:
            item = items_by_id.get(item_id)
            if item is None:
                continue
            cand_emb = embs_by_id.get(item_id)
            if cand_emb is None:
                continue
            cand_type = item.semantic_category or ""
            s = self.score(query_emb, query_type, cand_emb, cand_type)
            scored.append((s, item_id))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_k = scored[:k]

        results = []
        for s, item_id in top_k:
            item = items_by_id[item_id]
            results.append(
                {
                    "item_id": item_id,
                    "score": float(s),
                    "title": item.title or "",
                    "semantic_category": item.semantic_category or "",
                    "image_path": item.image_path or "",
                }
            )
        return results

    # ------------------------------------------------------------------
    # Properties / lifecycle
    # ------------------------------------------------------------------

    @property
    def current_version(self) -> str | None:
        """The version string of the currently-loaded checkpoint."""
        return self._version

    @property
    def is_loaded(self) -> bool:
        """True if a checkpoint is currently loaded."""
        return self._model is not None

    def reload(self) -> bool:
        """Hot-swap to the latest available checkpoint.

        Returns ``True`` if a new checkpoint was loaded, ``False`` if none
        was found or if it is the same version already loaded.
        """
        new_dir = latest_model_dir()
        if new_dir is None:
            logger.warning("reload(): no valid checkpoint found under %s", settings.models_dir)
            return False
        if self._model_dir is not None and new_dir.resolve() == self._model_dir.resolve():
            logger.info("reload(): already running latest checkpoint %s", self._version)
            return False
        self.load(new_dir)
        return True


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_service: ModelService | None = None


def get_model_service() -> ModelService:
    """Return the module-level :class:`ModelService` singleton (lazy-init)."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = ModelService()
    return _service
