"""
Tests for apply_bqsr task.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.apply_bqsr import apply_bqsr
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile, BQSRReport
from stargazer.types.reference import ReferenceFile


@pytest.mark.asyncio
async def test_apply_bqsr_recalibrates_bam(fixtures_db):
    """Test that apply_bqsr creates a recalibrated BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_apply_bqsr"

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
        bqsr_report=BQSRReport(
            path=FIXTURES_DIR / "NA12829_TP53_bqsr.table",
            keyvalues={"sample_id": sample_id, "tool": "gatk_base_recalibrator"},
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

    recalibrated = await apply_bqsr(alignment=alignment, ref=ref)

    assert isinstance(recalibrated, Alignment)
    assert recalibrated.sample_id == sample_id
    assert recalibrated.has_bqsr_applied

    result_bam = recalibrated.alignment
    assert result_bam is not None
    assert result_bam.keyvalues.get("bqsr_applied") == "true"
    assert result_bam.keyvalues.get("tool") == "gatk_apply_bqsr"
    # bqsr_report is not carried to the output (report was consumed)
    assert recalibrated.bqsr_report is None


@pytest.mark.asyncio
async def test_apply_bqsr_rejects_missing_report():
    """Test that apply_bqsr raises if bqsr_report is not set on alignment."""
    alignment = Alignment(
        sample_id="test",
        alignment=AlignmentFile(keyvalues={"duplicates_marked": "true"}),
    )
    with pytest.raises(ValueError, match="bqsr_report is not set"):
        await apply_bqsr(alignment=alignment, ref=Reference(build="test"))


@pytest.mark.asyncio
async def test_apply_bqsr_task_is_callable():
    """Test that apply_bqsr is a callable task."""
    assert callable(apply_bqsr)
    assert "apply_bqsr" in str(apply_bqsr)


@pytest.mark.asyncio
async def test_alignment_has_bqsr_applied_property():
    """Test has_bqsr_applied property on Alignment type."""
    non_bqsr_file = AlignmentFile(
        cid="QmNoBQSR",
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
    )
    assert not Alignment(sample_id="test", alignment=non_bqsr_file).has_bqsr_applied

    bqsr_file = AlignmentFile(
        cid="QmWithBQSR",
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
            "bqsr_applied": "true",
        },
    )
    assert Alignment(sample_id="test", alignment=bqsr_file).has_bqsr_applied


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_apply_bqsr_exported_from_package(self):
        """Test that apply_bqsr is accessible from stargazer.tasks."""
        from stargazer.tasks import apply_bqsr

        assert callable(apply_bqsr)
