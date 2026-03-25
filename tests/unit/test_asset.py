"""Tests for Asset base class."""

from pathlib import Path

from stargazer.assets.asset import Asset
from stargazer.assets.alignment import Alignment


class TestAssetRoundtrip:
    def test_roundtrip_with_path(self):
        original = Alignment(
            cid="Qm" + "a" * 44,
            path=Path("/tmp/test.bam"),
            sample_id="NA12878",
        )
        restored = Alignment.from_dict(original.to_dict())
        assert restored.cid == original.cid
        assert restored.path == original.path
        assert restored.sample_id == original.sample_id

    def test_roundtrip_without_path(self):
        original = Alignment(cid="Qm" + "b" * 44, sample_id="NA12878")
        restored = Alignment.from_dict(original.to_dict())
        assert restored.cid == original.cid
        assert restored.path is None
        assert restored.sample_id == original.sample_id

    def test_roundtrip_empty(self):
        original = Asset()
        restored = Asset.from_dict(original.to_dict())
        assert restored.cid == ""
        assert restored.path is None

    def test_to_dict_structure(self):
        asset = Alignment(cid="abc123", path=Path("/tmp/file.bam"), sample_id="S1")
        data = asset.to_dict()
        assert data["cid"] == "abc123"
        assert data["path"] == "/tmp/file.bam"
        assert data["keyvalues"]["sample_id"] == "S1"
        assert data["keyvalues"]["asset"] == "alignment"

    def test_to_dict_none_path(self):
        asset = Asset(cid="abc123")
        data = asset.to_dict()
        assert data["path"] is None

    def test_from_dict_round_trips_keyvalues(self):
        original = Alignment(cid="xyz", sample_id="S1", duplicates_marked=True)
        restored = Alignment.from_dict(original.to_dict())
        assert restored.sample_id == "S1"
        assert restored.duplicates_marked is True


class TestAssetDefaults:
    def test_default_cid_is_empty(self):
        assert Asset().cid == ""

    def test_default_path_is_none(self):
        assert Asset().path is None

    def test_asset_key_in_to_keyvalues(self):
        """Concrete subclasses include 'asset' key in to_keyvalues()."""
        from stargazer.assets.reference import Reference

        ref = Reference()
        assert ref.to_keyvalues().get("asset") == "reference"

    def test_base_asset_to_keyvalues_empty(self):
        """Base Asset with no _asset_key returns empty dict from to_keyvalues()."""
        assert Asset().to_keyvalues() == {}
