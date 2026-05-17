"""Tests for fitgraph.data.polyvore — Item/Outfit dataclasses and parsers."""

from pathlib import Path

import pytest

from fitgraph.data.polyvore import Item, load_item_metadata, load_outfits

FIXTURES = Path(__file__).parent.parent / "fixtures"
METADATA_FILE = FIXTURES / "metadata_sample.json"
OUTFITS_FILE = FIXTURES / "outfits_sample.json"
FAKE_IMAGES_DIR = Path("/fake/images")


class TestLoadItemMetadata:
    def test_returns_dict_keyed_by_item_id(self):
        items = load_item_metadata(METADATA_FILE, FAKE_IMAGES_DIR)
        assert isinstance(items, dict)
        assert set(items.keys()) == {"item001", "item002", "item003", "item004"}

    def test_item_fields_are_populated(self):
        items = load_item_metadata(METADATA_FILE, FAKE_IMAGES_DIR)
        jacket = items["item001"]
        assert isinstance(jacket, Item)
        assert jacket.id == "item001"
        assert jacket.title == "Blue Denim Jacket"
        assert jacket.description == "A classic blue denim jacket"
        assert jacket.category == "jackets"

    def test_image_path_constructed_correctly(self):
        items = load_item_metadata(METADATA_FILE, FAKE_IMAGES_DIR)
        assert items["item001"].image_path == FAKE_IMAGES_DIR / "item001.jpg"
        assert items["item004"].image_path == FAKE_IMAGES_DIR / "item004.jpg"

    def test_item_is_frozen(self):
        items = load_item_metadata(METADATA_FILE, FAKE_IMAGES_DIR)
        with pytest.raises((AttributeError, TypeError)):
            items["item001"].title = "modified"  # type: ignore[misc]

    def test_missing_description_defaults_to_empty_string(self):
        """item004 has an empty description — ensure it doesn't raise."""
        items = load_item_metadata(METADATA_FILE, FAKE_IMAGES_DIR)
        assert items["item004"].description == ""

    def test_image_path_is_path_object(self):
        items = load_item_metadata(METADATA_FILE, FAKE_IMAGES_DIR)
        assert isinstance(items["item001"].image_path, Path)


class TestLoadOutfits:
    def test_returns_list_of_outfits(self):
        outfits = load_outfits(OUTFITS_FILE)
        assert isinstance(outfits, list)
        assert len(outfits) == 3

    def test_outfit_ids_are_correct(self):
        outfits = load_outfits(OUTFITS_FILE)
        ids = {o.id for o in outfits}
        assert ids == {"outfit_a", "outfit_b", "outfit_c"}

    def test_outfit_item_ids_are_correct(self):
        outfits = load_outfits(OUTFITS_FILE)
        outfit_a = next(o for o in outfits if o.id == "outfit_a")
        assert set(outfit_a.item_ids) == {"item001", "item002", "item003"}

    def test_outfit_is_frozen(self):
        outfits = load_outfits(OUTFITS_FILE)
        with pytest.raises((AttributeError, TypeError)):
            outfits[0].id = "modified"  # type: ignore[misc]

    def test_outfit_item_ids_preserves_all_items(self):
        outfits = load_outfits(OUTFITS_FILE)
        outfit_b = next(o for o in outfits if o.id == "outfit_b")
        assert len(outfit_b.item_ids) == 2
        assert "item002" in outfit_b.item_ids
        assert "item004" in outfit_b.item_ids
