"""Qualitative outfit-grid renderer using Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_THUMB_SIZE = (224, 224)
_QUERY_BORDER = 6  # px, coloured border to mark query
_QUERY_BORDER_COLOR = (255, 80, 80)  # red
_CAPTION_HEIGHT = 24  # px reserved below each tile for score text
_FONT_SIZE = 16
_BACKGROUND = (240, 240, 240)
_PLACEHOLDER_COLOR = (200, 200, 200)


def _load_or_placeholder(path: Path) -> Image.Image:
    """Return a thumbnail-sized image or a grey placeholder if the file is missing/corrupt."""
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail(_THUMB_SIZE)
        # Pad to exact _THUMB_SIZE
        padded = Image.new("RGB", _THUMB_SIZE, _PLACEHOLDER_COLOR)
        offset_x = (_THUMB_SIZE[0] - img.width) // 2
        offset_y = (_THUMB_SIZE[1] - img.height) // 2
        padded.paste(img, (offset_x, offset_y))
        return padded
    except Exception:
        return Image.new("RGB", _THUMB_SIZE, _PLACEHOLDER_COLOR)


def render_outfit_grid(
    query_image: Path,
    suggestion_images: list[Path],
    out_path: Path,
    scores: list[float] | None = None,
) -> Path:
    """Compose a horizontal grid: query on left, suggestions to the right.

    Parameters
    ----------
    query_image:
        Path to the query item image.
    suggestion_images:
        Paths to the suggested/compatible item images.
    out_path:
        Destination PNG path.
    scores:
        Optional per-suggestion cosine-similarity scores for captions.

    Returns
    -------
    Path
        The ``out_path`` that was written.
    """
    tw, th = _THUMB_SIZE
    num_cols = 1 + len(suggestion_images)

    canvas_w = num_cols * tw
    canvas_h = th + _CAPTION_HEIGHT

    canvas = Image.new("RGB", (canvas_w, canvas_h), _BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", _FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()

    # --- query tile ---
    query_tile = _load_or_placeholder(query_image)
    # Draw a coloured border
    bordered = Image.new("RGB", (tw, th), _QUERY_BORDER_COLOR)
    b = _QUERY_BORDER
    bordered.paste(query_tile.crop((b, b, tw - b, th - b)), (b, b))
    canvas.paste(bordered, (0, 0))
    draw.text((tw // 2 - 20, th + 4), "query", fill=(80, 80, 80), font=font)

    # --- suggestion tiles ---
    for i, img_path in enumerate(suggestion_images):
        tile = _load_or_placeholder(img_path)
        x_off = (i + 1) * tw
        canvas.paste(tile, (x_off, 0))
        if scores is not None and i < len(scores):
            caption = f"{scores[i]:.3f}"
            draw.text(
                (x_off + tw // 2 - 20, th + 4),
                caption,
                fill=(50, 50, 50),
                font=font,
            )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(out_path), format="PNG")
    return out_path
