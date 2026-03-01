"""Tests for BQSRReport type (declared in alignment.py)."""

from pathlib import Path

from stargazer.types.component import ComponentFile
from stargazer.types.alignment import BQSRReport
from stargazer.types import COMPONENT_REGISTRY


class TestBQSRReport:
    def test_type_keyvalue(self):
        r = BQSRReport()
        assert r.keyvalues["type"] == "alignment"

    def test_component_keyvalue(self):
        r = BQSRReport()
        assert r.keyvalues["component"] == "bqsr_report"

    def test_is_component_file(self):
        assert isinstance(BQSRReport(), ComponentFile)

    def test_sample_id_via_keyvalues(self):
        r = BQSRReport()
        r.sample_id = "NA12829"
        assert r.keyvalues["sample_id"] == "NA12829"
        assert r.sample_id == "NA12829"

    def test_sample_id_default(self):
        r = BQSRReport()
        assert r.sample_id == ""

    def test_registered_in_component_registry(self):
        assert ("alignment", "bqsr_report") in COMPONENT_REGISTRY
        assert COMPONENT_REGISTRY[("alignment", "bqsr_report")] is BQSRReport

    def test_roundtrip(self):
        r = BQSRReport(
            cid="Qm" + "a" * 44,
            path=Path("/tmp/sample_bqsr.table"),
            keyvalues={
                "type": "alignment",
                "component": "bqsr_report",
                "sample_id": "NA12829",
            },
        )
        data = r.to_dict()
        restored = BQSRReport.from_dict(data)
        assert restored.cid == r.cid
        assert restored.path == r.path
        assert restored.keyvalues == r.keyvalues
