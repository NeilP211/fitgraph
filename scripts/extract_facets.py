"""Extract a dominant garment color + a brand label for each catalog item.

Color: load each item's image, drop the near-white product background, and
classify the remaining garment pixels into a fixed palette using vectorized
HSV rules; the majority bucket wins. Brand: the leading word of the title.

Adds items.color and items.brand columns (idempotent) and populates them.
Low memory: one downscaled image at a time. Run:
    .venv/bin/python scripts/extract_facets.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy import text

from fitgraph.db.session import get_engine

ROOT = Path(__file__).resolve().parents[1]
THUMB = 64  # downscale size for color analysis


def dominant_color(path: Path) -> str | None:
    """Return a palette color name for the garment in the image, or None."""
    try:
        img = Image.open(path).convert("RGB").resize((THUMB, THUMB))
    except Exception:
        return None
    rgb = np.asarray(img)
    # Near-white product background -> ignore.
    bg = (rgb[:, :, 0] > 235) & (rgb[:, :, 1] > 235) & (rgb[:, :, 2] > 235)
    garment = ~bg
    if garment.sum() < 0.04 * garment.size:
        return "white"

    hsv = np.asarray(img.convert("HSV")).astype(np.float32)
    H = hsv[:, :, 0] * 360.0 / 255.0
    S = hsv[:, :, 1] / 255.0
    V = hsv[:, :, 2] / 255.0
    H, S, V = H[garment], S[garment], V[garment]

    labels = np.full(H.shape, "", dtype="<U8")
    low_s = S < 0.15
    labels[low_s & (V > 0.85)] = "white"
    labels[low_s & (V > 0.45) & (V <= 0.85)] = "gray"
    labels[low_s & (V <= 0.45)] = "black"
    un = labels == ""
    beige = un & (S < 0.40) & (V > 0.70) & (H < 60)
    labels[beige] = "beige"
    un = labels == ""
    brown = un & (((H < 45) | (H >= 350)) & (V < 0.50))
    labels[brown] = "brown"
    labels[(labels == "") & ((H < 15) | (H >= 345))] = "red"
    labels[(labels == "") & (H < 45)] = "orange"
    labels[(labels == "") & (H < 65)] = "yellow"
    labels[(labels == "") & (H < 170)] = "green"
    labels[(labels == "") & (H < 255)] = "blue"
    labels[(labels == "") & (H < 290)] = "purple"
    labels[labels == ""] = "pink"

    vals, counts = np.unique(labels, return_counts=True)
    return str(vals[counts.argmax()])


def brand_of(title: str | None) -> str | None:
    """Leading word of the title as an approximate brand label."""
    if not title:
        return None
    first = title.strip().split()
    if not first:
        return None
    b = first[0].strip(",.&").strip()
    return b or None


def main() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE items ADD COLUMN IF NOT EXISTS color text"))
        conn.execute(text("ALTER TABLE items ADD COLUMN IF NOT EXISTS brand text"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS items_color_idx ON items (semantic_category, color)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS items_brand_idx ON items (semantic_category, brand)"))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, title, image_path FROM items")).fetchall()
    total = len(rows)
    print(f"items to process: {total}", flush=True)

    batch: list[dict] = []
    done = 0
    t0 = time.time()
    upd = text("UPDATE items SET color = :color, brand = :brand WHERE id = :id")
    for item_id, title, image_path in rows:
        color = None
        if image_path:
            p = Path(image_path)
            if not p.is_absolute():
                p = ROOT / p
            color = dominant_color(p)
        batch.append({"id": item_id, "color": color, "brand": brand_of(title)})
        done += 1
        if len(batch) >= 500:
            with engine.begin() as conn:
                conn.execute(upd, batch)
            batch.clear()
            if done % 5000 == 0:
                rate = done / (time.time() - t0)
                print(f"  {done}/{total} ({rate:.0f}/s)", flush=True)
    if batch:
        with engine.begin() as conn:
            conn.execute(upd, batch)

    with engine.connect() as conn:
        dist = conn.execute(
            text("SELECT color, count(*) FROM items WHERE color IS NOT NULL GROUP BY color ORDER BY count(*) DESC")
        ).fetchall()
    print(f"done in {time.time() - t0:.0f}s. color distribution:", flush=True)
    for c, n in dist:
        print(f"  {c}: {n}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
