"""
Tests for applybqsr task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.applybqsr import applybqsr
from stargazer.types import Reference, Alignment
from stargazer.utils.pinata import IpFile, default_client


def create_mock_bam(
    local_dir: Path, sample_id: str, test_cid: str
) -> tuple[Path, IpFile]:
    """
    Create a minimal mock BAM file for testing.

    Returns:
        Tuple of (bam_path, ipfile)
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    bam_path = local_dir / test_cid

    # Create minimal BAM-like content
    bam_path.write_bytes(b"BAM\x01mock_bam_content")

    ipfile = IpFile(
        id=f"test-{sample_id}-bam",
        cid=test_cid,
        name=f"{sample_id}.bam",
        size=bam_path.stat().st_size,
        keyvalues={
            "type": "alignment",
            "sample_id": sample_id,
            "tool": "fq2bam",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
        created_at=datetime.now(),
    )

    return bam_path, ipfile


def create_mock_reference(local_dir: Path, test_cid: str) -> tuple[Path, IpFile]:
    """
    Create a minimal valid reference FASTA for testing.

    Returns:
        Tuple of (ref_path, ipfile)
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    ref_path = local_dir / test_cid

    ref_content = """>chr17
GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC
"""
    ref_path.write_text(ref_content)

    ipfile = IpFile(
        id="test-ref",
        cid=test_cid,
        name="test_reference.fa",
        size=ref_path.stat().st_size,
        keyvalues={
            "type": "reference",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )

    return ref_path, ipfile


def create_mock_recal_report(
    local_dir: Path, sample_id: str, test_cid: str
) -> tuple[Path, IpFile]:
    """
    Create a mock BQSR recalibration report for testing.

    Returns:
        Tuple of (report_path, ipfile)
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    report_path = local_dir / test_cid

    # Create mock recalibration table content
    report_content = """#:GATKReport.v1.1:5
#:GATKTable:2:17:%s:%s:;
#:GATKTable:Arguments:Recalibration argument collection values used in this run
Argument                    Value
covariate                   ReadGroupCovariate,QualityScoreCovariate,ContextCovariate,CycleCovariate
"""
    report_path.write_text(report_content)

    ipfile = IpFile(
        id=f"test-{sample_id}-recal",
        cid=test_cid,
        name=f"{sample_id}_bqsr.table",
        size=report_path.stat().st_size,
        keyvalues={
            "type": "bqsr_report",
            "sample_id": sample_id,
            "tool": "gatk_baserecalibrator",
        },
        created_at=datetime.now(),
    )
    ipfile.local_path = report_path

    return report_path, ipfile


@pytest.mark.asyncio
async def test_applybqsr_recalibrates_bam():
    """Test that applybqsr creates a recalibrated BAM."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12878_applybqsr"
    test_cid_bam = "QmTestBAMApplyBQSR"
    test_cid_ref = "QmTestRefApplyBQSR"
    test_cid_recal = "QmTestRecalApplyBQSR"

    # Create mock files
    bam_path, bam_ipfile = create_mock_bam(
        default_client.local_dir, sample_id, test_cid_bam
    )
    ref_path, ref_ipfile = create_mock_reference(default_client.local_dir, test_cid_ref)
    recal_path, recal_ipfile = create_mock_recal_report(
        default_client.local_dir, sample_id, test_cid_recal
    )

    alignment = Alignment(
        sample_id=sample_id,
        bam_name=f"{sample_id}.bam",
        files=[bam_ipfile],
    )

    ref = Reference(
        ref_name="test_reference.fa",
        files=[ref_ipfile],
    )

    try:
        recalibrated = await applybqsr(
            alignment=alignment,
            ref=ref,
            recal_report=recal_ipfile,
        )

        # Verify result
        assert isinstance(recalibrated, Alignment)
        assert recalibrated.sample_id == sample_id
        assert recalibrated.has_bqsr_applied

        # Check metadata
        bam_file = None
        for f in recalibrated.files:
            if f.name == recalibrated.bam_name:
                bam_file = f
                break

        assert bam_file is not None
        assert bam_file.keyvalues.get("bqsr_applied") == "true"
        assert bam_file.keyvalues.get("tool") == "gatk_applybqsr"

    finally:
        # Cleanup
        if bam_path.exists():
            bam_path.unlink()
        if ref_path.exists():
            ref_path.unlink()
        if recal_path.exists():
            recal_path.unlink()


@pytest.mark.asyncio
async def test_applybqsr_task_is_callable():
    """Test that applybqsr is a callable task."""
    assert callable(applybqsr)
    assert "applybqsr" in str(applybqsr)


@pytest.mark.asyncio
async def test_alignment_has_bqsr_applied_property():
    """Test the has_bqsr_applied property on Alignment type."""
    # Test alignment without BQSR
    non_bqsr_ipfile = IpFile(
        id="test-no-bqsr",
        cid="QmNoBQSR",
        name="no_bqsr.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
        created_at=datetime.now(),
    )

    non_bqsr_alignment = Alignment(
        sample_id="test",
        bam_name="no_bqsr.bam",
        files=[non_bqsr_ipfile],
    )

    assert not non_bqsr_alignment.has_bqsr_applied

    # Test alignment with BQSR
    bqsr_ipfile = IpFile(
        id="test-with-bqsr",
        cid="QmWithBQSR",
        name="with_bqsr.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
            "bqsr_applied": "true",
        },
        created_at=datetime.now(),
    )

    bqsr_alignment = Alignment(
        sample_id="test",
        bam_name="with_bqsr.bam",
        files=[bqsr_ipfile],
    )

    assert bqsr_alignment.has_bqsr_applied


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_applybqsr_exported_from_package(self):
        """Test that applybqsr is accessible from stargazer.tasks."""
        from stargazer.tasks import applybqsr

        assert callable(applybqsr)
