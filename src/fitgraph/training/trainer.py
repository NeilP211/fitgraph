"""Mini-batch subgraph contrastive training for the HGAT model.

Design
------
- Builds a co-occurrence map from TRAIN outfits only (no test leakage).
- Each training step operates on a small HeteroData subgraph for the current
  batch of outfits, not the full graph.
- Neighbor (edge) dropout forces the inductive ``embed_features`` path to be
  trained alongside the graph path.
- Validation uses ONLY ``model.embed_features`` (no graph, no leakage).
"""

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
from torch_geometric.data import HeteroData

from fitgraph.models.hgat import HGAT
from fitgraph.training.loss import info_nce
from fitgraph.training.negatives import mine_hard_negatives

if TYPE_CHECKING:
    from fitgraph.config import Settings
    from fitgraph.data.polyvore import Outfit


class Trainer:
    """Mini-batch subgraph trainer for the HGAT model.

    Parameters
    ----------
    fused_tensor:
        Fused feature tensor aligned to ``all_ids``, shape ``(N, 896)``.
    clip_tensor:
        CLIP feature tensor aligned to ``all_ids``, shape ``(N, 512)``.
    all_ids:
        List of item_id strings in the same order as ``fused_tensor`` rows.
    train_outfits:
        List of Outfit objects from the train split.
    valid_outfits:
        List of Outfit objects from the valid split.
    settings:
        Configuration object.
    """

    def __init__(
        self,
        fused_tensor: torch.Tensor,
        clip_tensor: torch.Tensor,
        all_ids: list[str],
        train_outfits: list[Outfit],
        valid_outfits: list[Outfit],
        settings: Settings,
    ) -> None:
        self.settings = settings
        self.train_outfits = train_outfits
        self.valid_outfits = valid_outfits

        # Seed for determinism
        torch.manual_seed(settings.seed)
        random.seed(settings.seed)
        np.random.seed(settings.seed)

        self.device = torch.device(self._resolve_device())

        # Build item_id -> index mapping for the full item set
        self.all_ids: list[str] = all_ids
        self.id_to_idx: dict[str, int] = {iid: i for i, iid in enumerate(all_ids)}

        # Move feature tensors to device
        self.fused_tensor = fused_tensor.to(self.device)   # (N, 896)
        self.clip_tensor = clip_tensor.to(self.device)     # (N, 512)

        # Build the model
        self.model = HGAT(
            in_dim=fused_tensor.shape[1],
            hidden_dim=settings.hidden_dim,
            num_layers=settings.num_layers,
            num_heads=settings.num_heads,
            dropout=settings.dropout,
        ).to(self.device)

        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=settings.lr)
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=settings.epochs,
            eta_min=settings.lr * 0.05,
        )

        # Co-occurrence map: item_id -> set of co-worn item_ids (TRAIN ONLY)
        self._cooccur_ids: dict[str, set[str]] = self._build_cooccur_map(train_outfits)

        # Valid positive pairs (as index tuples into all_ids)
        self._valid_pairs: list[tuple[int, int]] = self._build_valid_pairs()
        self._valid_neg_pairs: list[tuple[int, int]] = self._build_valid_negatives()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_device() -> str:
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _build_cooccur_map(
        self, outfits: list[Outfit]
    ) -> dict[str, set[str]]:
        """Build item_id -> set of co-worn item_ids from the given outfits."""
        cooccur: dict[str, set[str]] = {}
        for outfit in outfits:
            valid = [iid for iid in outfit.item_ids if iid in self.id_to_idx]
            for iid in valid:
                if iid not in cooccur:
                    cooccur[iid] = set()
                cooccur[iid].update(other for other in valid if other != iid)
        return cooccur

    def _build_valid_pairs(self) -> list[tuple[int, int]]:
        """Build all co-worn garment index pairs from valid outfits."""
        pairs: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for outfit in self.valid_outfits:
            valid = [
                self.id_to_idx[iid]
                for iid in outfit.item_ids
                if iid in self.id_to_idx
            ]
            for i in range(len(valid)):
                for j in range(i + 1, len(valid)):
                    a, b = valid[i], valid[j]
                    key = (min(a, b), max(a, b))
                    if key not in seen:
                        seen.add(key)
                        pairs.append(key)
        return pairs

    def _build_valid_negatives(self) -> list[tuple[int, int]]:
        """Build random non-co-worn negative pairs equal in count to valid positives."""
        n = len(self._valid_pairs)
        N = len(self.all_ids)
        rng = random.Random(self.settings.seed + 1)

        # Build a fast co-occurrence lookup using indices
        cooccur_idx: dict[int, set[int]] = {}
        for iid, co_set in self._cooccur_ids.items():
            if iid not in self.id_to_idx:
                continue
            idx = self.id_to_idx[iid]
            cooccur_idx[idx] = {self.id_to_idx[co] for co in co_set if co in self.id_to_idx}

        negs: list[tuple[int, int]] = []
        attempts = 0
        max_attempts = n * 50
        while len(negs) < n and attempts < max_attempts:
            a = rng.randint(0, N - 1)
            b = rng.randint(0, N - 1)
            if a == b:
                attempts += 1
                continue
            if b not in cooccur_idx.get(a, set()):
                key = (min(a, b), max(a, b))
                negs.append(key)
            attempts += 1
        return negs[:n]

    def _build_batch_subgraph(
        self,
        outfit_batch: list[Outfit],
        edge_dropout: float,
    ) -> tuple[HeteroData, list[str], dict[str, int]]:
        """Build a small HeteroData subgraph for a batch of outfits.

        Returns
        -------
        subgraph:
            HeteroData with garment and outfit nodes for this batch.
        local_garment_ids:
            Ordered list of item_ids for garment nodes in the subgraph.
        local_id_to_idx:
            item_id -> local garment node index.
        """
        # Collect unique item ids in this batch
        used_ids: set[str] = set()
        for outfit in outfit_batch:
            for iid in outfit.item_ids:
                if iid in self.id_to_idx:
                    used_ids.add(iid)

        local_garment_ids: list[str] = sorted(used_ids)
        local_id_to_idx: dict[str, int] = {
            iid: i for i, iid in enumerate(local_garment_ids)
        }

        num_outfits = len(outfit_batch)

        # Garment features: gather from fused_tensor
        global_indices = torch.tensor(
            [self.id_to_idx[iid] for iid in local_garment_ids],
            dtype=torch.long,
            device=self.device,
        )
        garment_x = self.fused_tensor[global_indices]  # (num_garments, 896)

        # Outfit features: zeros (learned via message passing)
        outfit_x = torch.zeros((num_outfits, garment_x.shape[1]), device=self.device)

        # Build edges
        src_g: list[int] = []
        dst_o: list[int] = []
        for o_idx, outfit in enumerate(outfit_batch):
            for iid in outfit.item_ids:
                if iid in local_id_to_idx:
                    # Neighbor dropout: skip edge with probability edge_dropout
                    if edge_dropout > 0.0 and random.random() < edge_dropout:
                        continue
                    src_g.append(local_id_to_idx[iid])
                    dst_o.append(o_idx)

        if src_g:
            garment_in_outfit = torch.tensor(
                [src_g, dst_o], dtype=torch.long, device=self.device
            )
            outfit_contains_garment = torch.tensor(
                [dst_o, src_g], dtype=torch.long, device=self.device
            )
        else:
            garment_in_outfit = torch.zeros((2, 0), dtype=torch.long, device=self.device)
            outfit_contains_garment = torch.zeros((2, 0), dtype=torch.long, device=self.device)

        subgraph = HeteroData()
        subgraph["garment"].x = garment_x
        subgraph["outfit"].x = outfit_x
        subgraph["garment", "in", "outfit"].edge_index = garment_in_outfit
        subgraph["outfit", "contains", "garment"].edge_index = outfit_contains_garment

        return subgraph, local_garment_ids, local_id_to_idx

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
    # Validation: HONEST inductive only (no graph, no leakage)
    # ------------------------------------------------------------------

    def _validate(self) -> float:
        """Compute val AUC using ONLY embed_features (no graph context)."""
        if not self._valid_pairs or not self._valid_neg_pairs:
            return 0.5

        self.model.eval()
        with torch.no_grad():
            # Embed ALL items purely via feature projection (inductive path)
            all_emb = self.model.embed_features(self.fused_tensor)  # (N, D)

        labels: list[int] = []
        sims: list[float] = []

        # Positive pairs
        a_idx = torch.tensor([p[0] for p in self._valid_pairs], device=self.device)
        b_idx = torch.tensor([p[1] for p in self._valid_pairs], device=self.device)
        pos_sims = F.cosine_similarity(all_emb[a_idx], all_emb[b_idx]).cpu().tolist()
        labels.extend([1] * len(pos_sims))
        sims.extend(pos_sims)

        # Negative pairs
        na_idx = torch.tensor([p[0] for p in self._valid_neg_pairs], device=self.device)
        nb_idx = torch.tensor([p[1] for p in self._valid_neg_pairs], device=self.device)
        neg_sims = F.cosine_similarity(all_emb[na_idx], all_emb[nb_idx]).cpu().tolist()
        labels.extend([0] * len(neg_sims))
        sims.extend(neg_sims)

        if len(set(labels)) < 2:
            return 0.5

        return float(roc_auc_score(labels, sims))

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------

    def fit(self) -> dict:
        """Run the full training loop.

        Returns
        -------
        dict
            Summary with ``best_val_auc``, ``version_dir``, ``epochs``,
            ``epoch_losses``.
        """
        settings = self.settings
        rng = random.Random(settings.seed)

        best_val_auc = 0.0
        best_state: dict | None = None
        version_dir = self._next_version_dir()
        epoch_losses: list[float] = []

        for epoch in range(1, settings.epochs + 1):
            self.model.train()

            # Shuffle train outfits for this epoch
            outfits = list(self.train_outfits)
            rng.shuffle(outfits)

            batch_losses: list[float] = []

            for start in range(0, len(outfits), settings.batch_size):
                outfit_batch = outfits[start : start + settings.batch_size]
                if len(outfit_batch) < 2:
                    continue

                # Build subgraph with edge dropout
                subgraph, local_ids, local_id_to_idx = self._build_batch_subgraph(
                    outfit_batch, edge_dropout=settings.edge_dropout
                )

                if len(local_ids) < 2:
                    continue

                # Forward pass on small subgraph
                z = self.model(subgraph)  # (num_local_garments, D)

                # Build positive pairs from co-worn items in this batch
                anchor_local: list[int] = []
                positive_local: list[int] = []

                for outfit in outfit_batch:
                    valid = [
                        local_id_to_idx[iid]
                        for iid in outfit.item_ids
                        if iid in local_id_to_idx
                    ]
                    for i in range(len(valid)):
                        for j in range(i + 1, len(valid)):
                            anchor_local.append(valid[i])
                            positive_local.append(valid[j])

                if len(anchor_local) < 2:
                    continue

                # Randomly subsample pairs to avoid O(n^2) blowup
                max_pairs = settings.batch_size * 4
                if len(anchor_local) > max_pairs:
                    perm = rng.sample(range(len(anchor_local)), max_pairs)
                    anchor_local = [anchor_local[i] for i in perm]
                    positive_local = [positive_local[i] for i in perm]

                anchor_idx = torch.tensor(anchor_local, dtype=torch.long, device=self.device)
                positive_idx = torch.tensor(positive_local, dtype=torch.long, device=self.device)

                anchor_emb = z[anchor_idx]    # (B, D)
                positive_emb = z[positive_idx]  # (B, D)

                # Hard negative mining using CLIP features from the batch's items
                global_indices = torch.tensor(
                    [self.id_to_idx[iid] for iid in local_ids],
                    dtype=torch.long,
                    device=self.device,
                )
                pool_clip = self.clip_tensor[global_indices]  # (P, 512)
                anchor_clip = self.clip_tensor[
                    torch.tensor(
                        [self.id_to_idx[local_ids[i]] for i in anchor_local],
                        dtype=torch.long,
                        device=self.device,
                    )
                ]  # (B, 512)

                # Build forbidden sets (co-worn partners in local index space)
                # local_set maps local_idx -> item_id
                local_set = {v: k for k, v in local_id_to_idx.items()}
                forbidden: list[set[int]] = []
                for a_local_i in anchor_local:
                    a_id = local_set[a_local_i]
                    co_ids = self._cooccur_ids.get(a_id, set())
                    # Map co_ids to their local indices (those in the batch)
                    forbidden_local = {
                        local_id_to_idx[co_id]
                        for co_id in co_ids
                        if co_id in local_id_to_idx
                    }
                    forbidden.append(forbidden_local)

                hard_neg_local_idx = mine_hard_negatives(
                    anchor_clip,
                    pool_clip,
                    forbidden,
                    settings.num_hard_negatives,
                )  # (B, k)

                extra_neg_emb = z[hard_neg_local_idx.view(-1)]  # (B*k, D)

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

            # Honest inductive validation
            val_auc = self._validate()

            if val_auc > best_val_auc:
                best_val_auc = val_auc
                best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                torch.save(best_state, version_dir / "model.pt")
                meta_interim = {
                    "version": version_dir.name,
                    "epochs_run": epoch,
                    "best_val_auc": best_val_auc,
                    "hidden_dim": settings.hidden_dim,
                    "num_layers": settings.num_layers,
                    "num_heads": settings.num_heads,
                    "in_dim": self.fused_tensor.shape[1],
                    "edge_dropout": settings.edge_dropout,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                (version_dir / "meta.json").write_text(json.dumps(meta_interim, indent=2))

            # Step cosine LR schedule
            self.scheduler.step()

            print(
                f"Epoch {epoch:03d}/{settings.epochs} | "
                f"loss={mean_loss:.4f} | "
                f"val_auc={val_auc:.4f} | "
                f"best_auc={best_val_auc:.4f} | "
                f"lr={self.scheduler.get_last_lr()[0]:.2e}",
                flush=True,
            )

            if settings.wandb_enabled:
                import wandb  # noqa: PLC0415
                wandb.log({"epoch": epoch, "train_loss": mean_loss, "val_auc": val_auc})

        # Final checkpoint (may already be written above)
        if best_state is not None:
            torch.save(best_state, version_dir / "model.pt")
        else:
            torch.save(
                {k: v.cpu() for k, v in self.model.state_dict().items()},
                version_dir / "model.pt",
            )

        meta = {
            "version": version_dir.name,
            "epochs_run": settings.epochs,
            "best_val_auc": best_val_auc,
            "hidden_dim": settings.hidden_dim,
            "num_layers": settings.num_layers,
            "num_heads": settings.num_heads,
            "in_dim": self.fused_tensor.shape[1],
            "edge_dropout": settings.edge_dropout,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        (version_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        return {
            "best_val_auc": best_val_auc,
            "version_dir": str(version_dir),
            "epochs": settings.epochs,
            "epoch_losses": epoch_losses,
        }
