"""Tests for fitgraph.eval.grids — synthetic PIL images, no real dataset."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from fitgraph.eval.grids import render_outfit_grid


def _make_jpeg(path: Path, color: tuple[int, int, int] = (100, 150, 200)) -> Path:
    """Write a tiny solid-colour JPEG to *path* and return it."""
    img = Image.new("RGB", (64, 64), color)
    img.save(str(path), format="JPEG")
    return path


class TestRenderOutfitGrid:
    def test_produces_png_file(self, tmp_path: Path) -> None:
        query = _make_jpeg(tmp_path / "query.jpg")
        sug1 = _make_jpeg(tmp_path / "sug1.jpg", (200, 100, 50))
        sug2 = _make_jpeg(tmp_path / "sug2.jpg", (50, 200, 100))
        out = tmp_path / "grid.png"

        result = render_outfit_grid(query, [sug1, sug2], out)

        assert result == out
        assert out.exists()
        img = Image.open(out)
        assert img.format == "PNG"

    def test_output_has_sensible_dimensions(self, tmp_path: Path) -> None:
        query = _make_jpeg(tmp_path / "query.jpg")
        suggestions = [
            _make_jpeg(tmp_path / f"sug{i}.jpg") for i in range(3)
        ]
        out = tmp_path / "grid.png"
        render_outfit_grid(query, suggestions, out)

        img = Image.open(out)
        w, h = img.size
        assert w > 0
        assert h > 0
        # 4 tiles wide (query + 3 suggestions), each 224px → expect 4 * 224 = 896
        assert w == 4 * 224

    def test_missing_suggestion_does_not_crash(self, tmp_path: Path) -> None:
        query = _make_jpeg(tmp_path / "query.jpg")
        missing = tmp_path / "does_not_exist.jpg"
        out = tmp_path / "grid.png"

        # Should not raise even though suggestion file is missing
        render_outfit_grid(query, [missing], out)

        assert out.exists()
        img = Image.open(out)
        assert img.size[0] > 0

    def test_missing_query_does_not_crash(self, tmp_path: Path) -> None:
        query = tmp_path / "missing_query.jpg"
        sug = _make_jpeg(tmp_path / "sug.jpg")
        out = tmp_path / "grid.png"

        render_outfit_grid(query, [sug], out)

        assert out.exists()

    def test_scores_captions_accepted(self, tmp_path: Path) -> None:
        query = _make_jpeg(tmp_path / "q.jpg")
        sugs = [_make_jpeg(tmp_path / f"s{i}.jpg") for i in range(2)]
        out = tmp_path / "grid.png"

        render_outfit_grid(query, sugs, out, scores=[0.95, 0.87])

        assert out.exists()
        img = Image.open(out)
        assert img.size[0] > 0

    def test_no_suggestions(self, tmp_path: Path) -> None:
        query = _make_jpeg(tmp_path / "q.jpg")
        out = tmp_path / "grid.png"

        render_outfit_grid(query, [], out)

        assert out.exists()
        img = Image.open(out)
        # Only one tile (the query)
        assert img.size[0] == 224
