"""Tests for BQSRReport type (declared in alignment.py)."""

from pathlib import Path

from stargazer.types.asset import Asset
from stargazer.types.alignment import BQSRReport
from stargazer.types import ASSET_REGISTRY


class TestBQSRReport:
    def test_asset_keyvalue(self):
        r = BQSRReport()
        assert r.keyvalues["asset"] == "bqsr_report"

    def test_is_asset(self):
        assert isinstance(BQSRReport(), Asset)

    def test_sample_id_via_keyvalues(self):
        r = BQSRReport()
        r.sample_id = "NA12829"
        assert r.keyvalues["sample_id"] == "NA12829"
        assert r.sample_id == "NA12829"

    def test_sample_id_default(self):
        r = BQSRReport()
        assert r.sample_id == ""

    def test_registered_in_asset_registry(self):
        assert "bqsr_report" in ASSET_REGISTRY
        assert ASSET_REGISTRY["bqsr_report"] is BQSRReport

    def test_roundtrip(self):
        r = BQSRReport(
            cid="Qm" + "a" * 44,
            path=Path("/tmp/sample_bqsr.table"),
            keyvalues={
                "asset": "bqsr_report",
                "sample_id": "NA12829",
            },
        )
        data = r.to_dict()
        restored = BQSRReport.from_dict(data)
        assert restored.cid == r.cid
        assert restored.path == r.path
        assert restored.keyvalues == r.keyvalues
