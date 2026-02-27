"""Tests for ComponentFile base class."""

from pathlib import Path

from stargazer.utils.component import ComponentFile


class TestComponentFileRoundtrip:
    def test_roundtrip_with_path(self):
        original = ComponentFile(
            cid="Qm" + "a" * 44,
            path=Path("/tmp/test.fa"),
            keyvalues={"type": "reference", "component": "fasta"},
        )
        data = original.to_dict()
        restored = ComponentFile.from_dict(data)

        assert restored.cid == original.cid
        assert restored.path == original.path
        assert restored.keyvalues == original.keyvalues

    def test_roundtrip_without_path(self):
        original = ComponentFile(
            cid="Qm" + "b" * 44,
            keyvalues={"type": "alignment", "sample_id": "NA12878"},
        )
        data = original.to_dict()
        restored = ComponentFile.from_dict(data)

        assert restored.cid == original.cid
        assert restored.path is None
        assert restored.keyvalues == original.keyvalues

    def test_roundtrip_empty(self):
        original = ComponentFile()
        data = original.to_dict()
        restored = ComponentFile.from_dict(data)

        assert restored.cid == ""
        assert restored.path is None
        assert restored.keyvalues == {}

    def test_to_dict_structure(self):
        comp = ComponentFile(
            cid="abc123", path=Path("/tmp/file.bam"), keyvalues={"k": "v"}
        )
        data = comp.to_dict()

        assert data["cid"] == "abc123"
        assert data["path"] == "/tmp/file.bam"
        assert data["keyvalues"] == {"k": "v"}

    def test_to_dict_none_path(self):
        comp = ComponentFile(cid="abc123")
        data = comp.to_dict()
        assert data["path"] is None

    def test_from_dict_missing_path(self):
        data = {"cid": "xyz", "keyvalues": {"type": "reads"}}
        comp = ComponentFile.from_dict(data)
        assert comp.cid == "xyz"
        assert comp.path is None
        assert comp.keyvalues == {"type": "reads"}

    def test_from_dict_preserves_keyvalues(self):
        data = {
            "cid": "abc",
            "path": None,
            "keyvalues": {"type": "variants", "caller": "deepvariant"},
        }
        comp = ComponentFile.from_dict(data)
        assert comp.keyvalues["type"] == "variants"
        assert comp.keyvalues["caller"] == "deepvariant"


class TestComponentFileDefaults:
    def test_default_cid_is_empty(self):
        comp = ComponentFile()
        assert comp.cid == ""

    def test_default_path_is_none(self):
        comp = ComponentFile()
        assert comp.path is None

    def test_default_keyvalues_is_empty_dict(self):
        comp = ComponentFile()
        assert comp.keyvalues == {}

    def test_keyvalues_not_shared_between_instances(self):
        """Verify each instance gets its own keyvalues dict."""
        a = ComponentFile()
        b = ComponentFile()
        a.keyvalues["x"] = "1"
        assert "x" not in b.keyvalues
