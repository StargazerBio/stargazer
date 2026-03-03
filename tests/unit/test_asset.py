"""Tests for Asset base class."""

from pathlib import Path

from stargazer.types.asset import Asset


class TestAssetRoundtrip:
    def test_roundtrip_with_path(self):
        original = Asset(
            cid="Qm" + "a" * 44,
            path=Path("/tmp/test.fa"),
            keyvalues={"asset": "reference", "build": "GRCh38"},
        )
        data = original.to_dict()
        restored = Asset.from_dict(data)

        assert restored.cid == original.cid
        assert restored.path == original.path
        assert restored.keyvalues == original.keyvalues

    def test_roundtrip_without_path(self):
        original = Asset(
            cid="Qm" + "b" * 44,
            keyvalues={"asset": "alignment", "sample_id": "NA12878"},
        )
        data = original.to_dict()
        restored = Asset.from_dict(data)

        assert restored.cid == original.cid
        assert restored.path is None
        assert restored.keyvalues == original.keyvalues

    def test_roundtrip_empty(self):
        original = Asset()
        data = original.to_dict()
        restored = Asset.from_dict(data)

        assert restored.cid == ""
        assert restored.path is None
        assert restored.keyvalues == {}

    def test_to_dict_structure(self):
        asset = Asset(cid="abc123", path=Path("/tmp/file.bam"), keyvalues={"k": "v"})
        data = asset.to_dict()

        assert data["cid"] == "abc123"
        assert data["path"] == "/tmp/file.bam"
        assert data["keyvalues"] == {"k": "v"}

    def test_to_dict_none_path(self):
        asset = Asset(cid="abc123")
        data = asset.to_dict()
        assert data["path"] is None

    def test_from_dict_missing_path(self):
        data = {"cid": "xyz", "keyvalues": {"asset": "r1"}}
        asset = Asset.from_dict(data)
        assert asset.cid == "xyz"
        assert asset.path is None
        assert asset.keyvalues == {"asset": "r1"}

    def test_from_dict_preserves_keyvalues(self):
        data = {
            "cid": "abc",
            "path": None,
            "keyvalues": {"asset": "variants", "caller": "deepvariant"},
        }
        asset = Asset.from_dict(data)
        assert asset.keyvalues["asset"] == "variants"
        assert asset.keyvalues["caller"] == "deepvariant"


class TestAssetDefaults:
    def test_default_cid_is_empty(self):
        assert Asset().cid == ""

    def test_default_path_is_none(self):
        assert Asset().path is None

    def test_default_keyvalues_is_empty_dict(self):
        assert Asset().keyvalues == {}

    def test_keyvalues_not_shared_between_instances(self):
        """Verify each instance gets its own keyvalues dict."""
        a = Asset()
        b = Asset()
        a.keyvalues["x"] = "1"
        assert "x" not in b.keyvalues

    def test_asset_key_auto_set_in_keyvalues(self):
        """Concrete subclasses auto-set 'asset' keyvalue in __post_init__."""
        from stargazer.types.reference import Reference

        ref = Reference()
        assert ref.keyvalues.get("asset") == "reference"

    def test_base_asset_no_auto_keyvalue(self):
        """Base Asset with no _asset_key does not set 'asset' keyvalue."""
        a = Asset()
        assert "asset" not in a.keyvalues
