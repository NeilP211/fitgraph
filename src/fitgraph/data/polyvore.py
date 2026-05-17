"""Polyvore Outfits dataset dataclasses and file parsers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Item:
    """A single clothing item from the Polyvore dataset."""

    id: str
    category: str  # semantic_category
    title: str
    description: str
    image_path: Path


@dataclass(frozen=True)
class Outfit:
    """A complete outfit (set) from the Polyvore dataset."""

    id: str  # set_id
    item_ids: list[str]


def load_item_metadata(metadata_path: Path, images_dir: Path) -> dict[str, Item]:
    """Parse polyvore_item_metadata.json into a dict of item_id -> Item.

    Missing fields default to empty strings. image_path is constructed as
    ``images_dir / f"{item_id}.jpg"``.
    """
    with metadata_path.open() as fh:
        raw: dict[str, dict] = json.load(fh)

    items: dict[str, Item] = {}
    for item_id, meta in raw.items():
        items[item_id] = Item(
            id=item_id,
            category=meta.get("semantic_category", "") or "",
            title=meta.get("title", "") or "",
            description=meta.get("description", "") or "",
            image_path=images_dir / f"{item_id}.jpg",
        )
    return items


def load_outfits(split_json_path: Path) -> list[Outfit]:
    """Parse a disjoint/{train,valid,test}.json file into Outfit objects.

    Each entry is expected to have the shape:
        {"set_id": str, "items": [{"item_id": str, "index": int}, ...], ...}
    """
    with split_json_path.open() as fh:
        raw: list[dict] = json.load(fh)

    outfits: list[Outfit] = []
    for entry in raw:
        item_ids = [it["item_id"] for it in entry.get("items", [])]
        outfits.append(Outfit(id=entry["set_id"], item_ids=item_ids))
    return outfits
