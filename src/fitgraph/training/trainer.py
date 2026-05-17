"""Contrastive training loop for the HGAT model."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score

from fitgraph.models.hgat import HGAT
from fitgraph.training.loss import info_nce
from fitgraph.training.negatives import mine_hard_negatives

if TYPE_CHECKING:
    from fitgraph.config import Settings
    from fitgraph.graph.builder import GraphBundle


class Trainer:
    """Manages contrastive training of an HGAT model.

    Parameters
    ----------
    bundle:
        GraphBundle containing the HeteroData graph and index maps.
    clip_emb:
        CLIP embeddings aligned to garment node order, shape
        ``(num_garments, 512)``.
    settings:
        Configuration object (hidden_dim, lr, epochs, batch_size, etc.).
    """

    def __init__(
        self,
        bundle: GraphBundle,
        clip_emb: np.ndarray,
        settings: Settings,
    ) -> None:
        self.bundle = bundle
        self.settings = settings

        # Seed for determinism
        torch.manual_seed(settings.seed)
        random.seed(settings.seed)
        np.random.seed(settings.seed)

        self.device = torch.device(self._resolve_device())

        # Move graph to device
        self.data = bundle.data.to(self.device)

        # CLIP embeddings on device
        self.clip_emb = torch.tensor(clip_emb, dtype=torch.float32, device=self.device)

        # Build the model
        self.model = HGAT(
            in_dim=896,
            hidden_dim=settings.hidden_dim,
            num_layers=settings.num_layers,
            num_heads=settings.num_heads,
            dropout=settings.dropout,
        ).to(self.device)

        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=settings.lr)

        # Precompute co-occurrence map and positive pairs
        self._cooccur: dict[int, set[int]] = self._build_cooccur_map()
        self._train_pairs: list[tuple[int, int]] = self._build_pairs("train")
        self._valid_pairs: list[tuple[int, int]] = self._build_pairs("valid")
        self._valid_neg_pairs: list[tuple[int, int]] = self._build_valid_negatives()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_device() -> str:
        """Return best available device."""
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _build_cooccur_map(self) -> dict[int, set[int]]:
        """Build garment_idx -> set of co-worn garment_idxs across ALL outfits."""
        # Use numpy for fast vectorised operations; ensure CPU tensors
        edge_index = self.bundle.data["garment", "in", "outfit"].edge_index
        g_arr = edge_index[0].cpu().numpy()  # (E,) garment indices
        o_arr = edge_index[1].cpu().numpy()  # (E,) outfit indices

        # Build outfit -> garments map via numpy groupby
        sort_idx = np.argsort(o_arr, kind="stable")
        g_sorted = g_arr[sort_idx]
        o_sorted = o_arr[sort_idx]
        _, outfit_start, outfit_counts = np.unique(
            o_sorted, return_index=True, return_counts=True
        )

        cooccur: dict[int, set[int]] = {}
        for start, count in zip(outfit_start, outfit_counts, strict=True):
            garments = g_sorted[start : start + count].tolist()
            for g in garments:
                if g not in cooccur:
                    cooccur[g] = set()
                cooccur[g].update(g2 for g2 in garments if g2 != g)

        return cooccur

    def _build_pairs(self, split: str) -> list[tuple[int, int]]:
        """Build all unordered co-worn garment pairs from outfits in ``split``."""
        edge_index = self.bundle.data["garment", "in", "outfit"].edge_index
        g_arr = edge_index[0].cpu().numpy()  # (E,)
        o_arr = edge_index[1].cpu().numpy()  # (E,)

        # Mask to split outfits
        split_mask = np.array(
            [s == split for s in self.bundle.outfit_split], dtype=bool
        )  # (num_outfits,)
        edge_mask = split_mask[o_arr]  # (E,)
        g_split = g_arr[edge_mask]
        o_split = o_arr[edge_mask]

        # Group by outfit
        sort_idx = np.argsort(o_split, kind="stable")
        g_sorted = g_split[sort_idx]
        o_sorted = o_split[sort_idx]
        _, outfit_start, outfit_counts = np.unique(
            o_sorted, return_index=True, return_counts=True
        )

        pairs: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for start, count in zip(outfit_start, outfit_counts, strict=True):
            garments = g_sorted[start : start + count].tolist()
            for i in range(len(garments)):
                for j in range(i + 1, len(garments)):
                    a, b = garments[i], garments[j]
                    key = (min(a, b), max(a, b))
                    if key not in seen:
                        seen.add(key)
                        pairs.append(key)

        return pairs

    def _build_valid_negatives(self) -> list[tuple[int, int]]:
        """Build random non-co-worn negative pairs equal in count to valid positives."""
        n = len(self._valid_pairs)
        num_garments = len(self.bundle.garment_ids)
        rng = random.Random(self.settings.seed + 1)

        negs: list[tuple[int, int]] = []
        attempts = 0
        max_attempts = n * 20
        while len(negs) < n and attempts < max_attempts:
            a = rng.randint(0, num_garments - 1)
            b = rng.randint(0, num_garments - 1)
            if a == b:
                attempts += 1
                continue
            # Not co-worn
            if b not in self._cooccur.get(a, set()):
                key = (min(a, b), max(a, b))
                negs.append(key)
            attempts += 1

        return negs[:n]

    def _next_version_dir(self) -> Path:
        """Return the next versioned model directory (v0, v1, v2, …)."""
        models_dir = Path(self.settings.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        while (models_dir / f"v{n}").exists():
            n += 1
        version_dir = models_dir / f"v{n}"
        version_dir.mkdir(parents=True)
        return version_dir

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------

    def fit(self) -> dict:
        """Run the full training loop.

        Returns
        -------
        dict
            Summary with ``best_val_auc``, ``version_dir``, ``epochs``.
        """
        settings = self.settings
        rng = random.Random(settings.seed)

        best_val_auc = 0.0
        best_state: dict | None = None
        version_dir = self._next_version_dir()

        epoch_losses: list[float] = []

        for epoch in range(1, settings.epochs + 1):
            self.model.train()
            # Shuffle training pairs
            pairs = list(self._train_pairs)
            rng.shuffle(pairs)

            batch_losses: list[float] = []

            for start in range(0, len(pairs), settings.batch_size):
                batch = pairs[start : start + settings.batch_size]
                if len(batch) < 2:
                    continue

                anchors_idx = torch.tensor(
                    [p[0] for p in batch], dtype=torch.long, device=self.device
                )
                positives_idx = torch.tensor(
                    [p[1] for p in batch], dtype=torch.long, device=self.device
                )

                # Full-graph forward to get all garment embeddings
                all_emb = self.model(self.data)  # (num_garments, hidden_dim)

                anchor_emb = all_emb[anchors_idx]   # (B, D)
                positive_emb = all_emb[positives_idx]  # (B, D)

                # Hard negative mining using CLIP embeddings
                pool_size = min(512, len(self.bundle.garment_ids))
                pool_indices_list = random.sample(
                    range(len(self.bundle.garment_ids)), pool_size
                )
                pool_indices = torch.tensor(
                    pool_indices_list, dtype=torch.long, device=self.device
                )
                pool_clip = self.clip_emb[pool_indices]  # (P, 512)
                anchor_clip = self.clip_emb[anchors_idx]  # (B, 512)

                # Build forbidden sets efficiently (all on CPU)
                B = len(batch)
                anchors_cpu = anchors_idx.cpu().tolist()
                pool_set = {g_idx: pos for pos, g_idx in enumerate(pool_indices_list)}
                forbidden: list[set[int]] = []
                for a_cpu in anchors_cpu:
                    cooccur_set = self._cooccur.get(a_cpu, set())
                    forbidden_pool_pos = {
                        pool_set[g] for g in cooccur_set if g in pool_set
                    }
                    forbidden.append(forbidden_pool_pos)

                hard_neg_pool_idx = mine_hard_negatives(
                    anchor_clip, pool_clip, forbidden, settings.num_hard_negatives
                )  # (B, k)

                hard_neg_global_idx = pool_indices[hard_neg_pool_idx.view(-1)].view(
                    B, settings.num_hard_negatives
                )
                extra_neg_emb = all_emb[hard_neg_global_idx.view(-1)]  # (B*k, D)

                loss = info_nce(
                    anchor_emb,
                    positive_emb,
                    extra_negatives=extra_neg_emb,
                    temperature=settings.temperature,
                )

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                batch_losses.append(float(loss.detach()))

            mean_loss = float(np.mean(batch_losses)) if batch_losses else float("nan")
            epoch_losses.append(mean_loss)

            # Validation
            val_auc = self._validate()

            # Track best and save checkpoint immediately when improved
            if val_auc > best_val_auc:
                best_val_auc = val_auc
                best_state = {
                    k: v.cpu().clone() for k, v in self.model.state_dict().items()
                }
                # Save best checkpoint eagerly so it survives early termination
                torch.save(best_state, version_dir / "model.pt")
                meta_interim = {
                    "version": version_dir.name,
                    "epochs": epoch,
                    "best_val_auc": best_val_auc,
                    "hidden_dim": settings.hidden_dim,
                    "num_layers": settings.num_layers,
                    "num_heads": settings.num_heads,
                    "in_dim": 896,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                (version_dir / "meta.json").write_text(
                    json.dumps(meta_interim, indent=2)
                )

            print(
                f"Epoch {epoch:03d}/{settings.epochs} | "
                f"loss={mean_loss:.4f} | "
                f"val_auc={val_auc:.4f} | "
                f"best_auc={best_val_auc:.4f}",
                flush=True,
            )

            if settings.wandb_enabled:
                import wandb  # noqa: PLC0415

                wandb.log(
                    {
                        "epoch": epoch,
                        "train_loss": mean_loss,
                        "val_auc": val_auc,
                    }
                )

        # Final checkpoint save (may already be written per-epoch above)
        if best_state is not None:
            torch.save(best_state, version_dir / "model.pt")
        else:
            # Edge case: save current state
            torch.save(
                {k: v.cpu() for k, v in self.model.state_dict().items()},
                version_dir / "model.pt",
            )

        meta = {
            "version": version_dir.name,
            "epochs": settings.epochs,
            "best_val_auc": best_val_auc,
            "hidden_dim": settings.hidden_dim,
            "num_layers": settings.num_layers,
            "num_heads": settings.num_heads,
            "in_dim": 896,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        (version_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        return {
            "best_val_auc": best_val_auc,
            "version_dir": str(version_dir),
            "epochs": settings.epochs,
            "epoch_losses": epoch_losses,
        }

    def _validate(self) -> float:
        """Compute pairwise compatibility AUC on validation pairs."""
        if not self._valid_pairs or not self._valid_neg_pairs:
            return 0.5

        self.model.eval()
        with torch.no_grad():
            all_emb = self.model(self.data)  # (num_garments, hidden_dim)

        labels: list[int] = []
        sims: list[float] = []

        # Positive pairs
        for a_idx, b_idx in self._valid_pairs:
            ea = all_emb[a_idx]
            eb = all_emb[b_idx]
            sim = float(F.cosine_similarity(ea.unsqueeze(0), eb.unsqueeze(0)))
            labels.append(1)
            sims.append(sim)

        # Negative pairs
        for a_idx, b_idx in self._valid_neg_pairs:
            ea = all_emb[a_idx]
            eb = all_emb[b_idx]
            sim = float(F.cosine_similarity(ea.unsqueeze(0), eb.unsqueeze(0)))
            labels.append(0)
            sims.append(sim)

        if len(set(labels)) < 2:
            return 0.5

        return float(roc_auc_score(labels, sims))
