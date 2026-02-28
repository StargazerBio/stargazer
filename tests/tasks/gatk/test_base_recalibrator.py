"""
Tests for base_recalibrator task.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

import stargazer.utils.storage as _storage_mod
from stargazer.tasks.gatk.base_recalibrator import base_recalibrator
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile
from stargazer.types.component import ComponentFile
from stargazer.types.reference import ReferenceFile


KNOWN_SITES_VCF = "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf"


@pytest.mark.asyncio
async def test_base_recalibrator_creates_report(fixtures_db):
    """Test that base_recalibrator creates a recalibration report."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_bqsr"

    alignment = Alignment(
        sample_id=sample_id,
        alignment=AlignmentFile(
            path=FIXTURES_DIR / "NA12829_TP53_markdup.bam",
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": sample_id,
                "tool": "gatk_mark_duplicates",
                "sorted": "coordinate",
                "duplicates_marked": "true",
            },
        ),
    )

    ref = Reference(
        build="GRCh38",
        fasta=ReferenceFile(
            path=FIXTURES_DIR / "GRCh38_TP53.fa",
            keyvalues={"type": "reference", "component": "fasta", "build": "GRCh38"},
        ),
    )

    fixtures_db()  # checkout: switch to isolated work dir

    # Upload known sites (VCF + index) into work DB so the task's query() can find them
    # GATK requires the .idx file to be co-located with the VCF for random access
    await _storage_mod.default_client.upload(
        ComponentFile(
            path=FIXTURES_DIR / KNOWN_SITES_VCF,
            keyvalues={"type": "known_sites", "name": KNOWN_SITES_VCF},
        )
    )
    await _storage_mod.default_client.upload(
        ComponentFile(
            path=FIXTURES_DIR / f"{KNOWN_SITES_VCF}.idx",
            keyvalues={
                "type": "known_sites",
                "component": "index",
                "name": f"{KNOWN_SITES_VCF}.idx",
            },
        )
    )

    recal_report = await base_recalibrator(
        alignment=alignment,
        ref=ref,
        known_sites=[KNOWN_SITES_VCF],
    )

    assert isinstance(recal_report, ComponentFile)
    assert recal_report.keyvalues.get("type") == "bqsr_report"
    assert recal_report.keyvalues.get("sample_id") == sample_id


@pytest.mark.asyncio
async def test_base_recalibrator_rejects_empty_known_sites():
    """Test that base_recalibrator raises error for empty known_sites."""
    with pytest.raises(ValueError, match="known_sites list cannot be empty"):
        await base_recalibrator(
            alignment=Alignment(sample_id="test"),
            ref=Reference(build="test"),
            known_sites=[],
        )


@pytest.mark.asyncio
async def test_base_recalibrator_task_is_callable():
    """Test that base_recalibrator is a callable task."""
    assert callable(base_recalibrator)
    assert "base_recalibrator" in str(base_recalibrator)


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_base_recalibrator_exported_from_package(self):
        """Test that base_recalibrator is accessible from stargazer.tasks."""
        from stargazer.tasks import base_recalibrator

        assert callable(base_recalibrator)
