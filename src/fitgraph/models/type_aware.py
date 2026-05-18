"""Type-aware embedding subspaces for outfit compatibility.

Implements the Vasileva et al. 2018 "type-aware embeddings" technique.

Motivation
----------
A single shared embedding space models "is similar to" well but
"goes well with" (complementarity) poorly — a top should pair with bottoms,
not other tops.  Type-aware embeddings fix this: compatibility between an
item of type A and an item of type B is measured in a learned
*type-pair-specific subspace*.

The subspace for a type-pair is realised as a learned non-negative mask
applied element-wise to the shared embedding before cosine similarity.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class TypeSpaceIndex:
    """Maps an unordered pair of coarse item types to a subspace id.

    Built from the pickled ``typespaces.p`` list of ``(type_a, type_b)`` tuples.
    The list index is the subspace id.  Pairs are treated as unordered, so the
    lookup is keyed by the sorted tuple.  Any pair whose types are not present
    in ``typespaces.p`` (unknown / missing categories) falls back to one extra
    "general" subspace whose id is ``len(typespaces)``.

    Parameters
    ----------
    typespaces:
        List of ``(type_a, type_b)`` tuples.  The position in the list is the
        subspace id.
    """

    def __init__(self, typespaces: list[tuple[str, str]]) -> None:
        # Store the raw list (as plain tuples) so the index is picklable.
        self._typespaces: list[tuple[str, str]] = [
            (str(a), str(b)) for a, b in typespaces
        ]
        self._fallback_id: int = len(self._typespaces)
        # Lookup keyed by sorted tuple -> subspace id.
        self._lookup: dict[tuple[str, str], int] = {}
        for idx, (a, b) in enumerate(self._typespaces):
            key = (a, b) if a <= b else (b, a)
            # First occurrence wins (typespaces.p has no duplicate sorted pairs).
            self._lookup.setdefault(key, idx)

    @classmethod
    def from_file(cls, path: str | Path) -> TypeSpaceIndex:
        """Build a :class:`TypeSpaceIndex` from a pickled ``typespaces.p`` file."""
        with Path(path).open("rb") as fh:
            typespaces = pickle.load(fh)  # noqa: S301 - trusted dataset file
        if not isinstance(typespaces, list):
            raise TypeError(
                f"typespaces.p must contain a list, got {type(typespaces)!r}"
            )
        return cls([tuple(t) for t in typespaces])

    def space_of(self, type_a: str, type_b: str) -> int:
        """Return the subspace id for the unordered type-pair ``(type_a, type_b)``.

        Unknown pairs (either type missing from ``typespaces.p``) map to the
        fallback "general" subspace id (``num_spaces - 1``).
        """
        a, b = str(type_a), str(type_b)
        key = (a, b) if a <= b else (b, a)
        return self._lookup.get(key, self._fallback_id)

    @property
    def num_spaces(self) -> int:
        """Total number of subspaces = len(typespaces) + 1 fallback space."""
        return len(self._typespaces) + 1

    @property
    def fallback_id(self) -> int:
        """The subspace id of the general / fallback space."""
        return self._fallback_id

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of this index."""
        return {
            "typespaces": [list(t) for t in self._typespaces],
            "num_spaces": self.num_spaces,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> TypeSpaceIndex:
        """Reconstruct a :class:`TypeSpaceIndex` from :meth:`to_dict` output."""
        return cls([tuple(t) for t in payload["typespaces"]])

    def save_json(self, path: str | Path) -> None:
        """Persist this index to a JSON file."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load_json(cls, path: str | Path) -> TypeSpaceIndex:
        """Load a :class:`TypeSpaceIndex` previously saved with :meth:`save_json`."""
        return cls.from_dict(json.loads(Path(path).read_text()))

    # Picklable via plain attributes; provide explicit support for clarity.
    def __getstate__(self) -> dict:
        return {"typespaces": self._typespaces}

    def __setstate__(self, state: dict) -> None:
        self.__init__(state["typespaces"])  # type: ignore[misc]


class TypeAwareScorer(nn.Module):
    """Scores item-pair compatibility in a learned type-pair-specific subspace.

    Each subspace owns a learned non-negative mask (``softplus`` of a free
    parameter) applied element-wise to the shared embeddings before cosine
    similarity.  With the masks initialised to ones, ``softplus(1) ≈ 1.31`` is a
    positive constant, so the projection is a uniform scaling and the resulting
    cosine similarity equals plain cosine similarity at initialisation.

    Parameters
    ----------
    num_spaces:
        Number of type-pair subspaces (including the fallback space).
    dim:
        Dimensionality of the shared item embeddings.
    """

    def __init__(self, num_spaces: int, dim: int) -> None:
        super().__init__()
        self.num_spaces = num_spaces
        self.dim = dim
        # Learnable masks, initialised to ones so the model starts ≈ plain cosine.
        self.masks = nn.Parameter(torch.ones(num_spaces, dim))

    def _projection(self, space_ids: Tensor) -> Tensor:
        """Return the non-negative projection mask for each given space id.

        ``space_ids`` of any shape ``S`` -> projection of shape ``(*S, dim)``.
        """
        proj = F.softplus(self.masks)  # (num_spaces, dim)
        return proj[space_ids]  # (*space_ids.shape, dim)

    def score_pairs(
        self, emb_a: Tensor, emb_b: Tensor, space_ids: Tensor
    ) -> Tensor:
        """Type-aware cosine similarity for aligned pairs.

        Parameters
        ----------
        emb_a, emb_b:
            Shared item embeddings, shape ``(B, dim)``.
        space_ids:
            Long tensor ``(B,)`` of the type-pair subspace for each pair.

        Returns
        -------
        Tensor
            Type-aware cosine similarities, shape ``(B,)``, in ``[-1, 1]``.
        """
        proj = self._projection(space_ids)  # (B, dim)
        pa = F.normalize(emb_a * proj, p=2, dim=-1)
        pb = F.normalize(emb_b * proj, p=2, dim=-1)
        return (pa * pb).sum(dim=-1)  # (B,)

    def score_matrix(
        self,
        anchors: Tensor,
        candidates: Tensor,
        space_ids: Tensor,
        anchor_chunk: int = 256,
    ) -> Tensor:
        """Type-aware cosine similarity for every anchor-candidate pair.

        Memory-bounded implementation: anchors are processed in chunks of at
        most ``anchor_chunk`` rows so that the peak intermediate tensor is
        ``(anchor_chunk, C, dim)`` rather than ``(B, C, dim)``.  With the
        default ``anchor_chunk=256`` and typical C=1500, dim=256, peak memory
        is ~256 * 1500 * 256 * 4 bytes ≈ 390 MB instead of B * C * dim * 4
        which can reach tens of GB for large batches.  The numerical result is
        identical to the non-chunked version.

        Parameters
        ----------
        anchors:
            Shared anchor embeddings, shape ``(B, dim)``.
        candidates:
            Shared candidate embeddings, shape ``(C, dim)``.
        space_ids:
            Long tensor ``(B, C)`` — the type-pair subspace for each
            anchor-candidate pair.
        anchor_chunk:
            Maximum number of anchor rows processed at once.  Controls the
            peak memory of the intermediate ``(chunk, C, dim)`` projection
            tensor.  Defaults to 256.

        Returns
        -------
        Tensor
            Type-aware cosine similarities, shape ``(B, C)``, in ``[-1, 1]``.
        """
        B = anchors.size(0)
        chunks: list[Tensor] = []
        for start in range(0, B, anchor_chunk):
            end = min(start + anchor_chunk, B)
            anc_chunk = anchors[start:end]          # (chunk, dim)
            sid_chunk = space_ids[start:end]        # (chunk, C)
            proj = self._projection(sid_chunk)      # (chunk, C, dim)
            # Broadcast anchor chunk over C, candidates over chunk.
            a = anc_chunk.unsqueeze(1) * proj       # (chunk, C, dim)
            c = candidates.unsqueeze(0) * proj      # (chunk, C, dim)
            a = F.normalize(a, p=2, dim=-1)
            c = F.normalize(c, p=2, dim=-1)
            chunks.append((a * c).sum(dim=-1))      # (chunk, C)
        return torch.cat(chunks, dim=0)             # (B, C)
