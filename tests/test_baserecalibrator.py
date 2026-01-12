"""
Tests for baserecalibrator task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.baserecalibrator import baserecalibrator
from stargazer.types import Reference, Alignment
from stargazer.utils.pinata import IpFile, default_client


def create_mock_bam(
    cache_dir: Path, sample_id: str, test_cid: str
) -> tuple[Path, IpFile]:
    """
    Create a minimal mock BAM file for testing.

    Returns:
        Tuple of (bam_path, ipfile)
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    bam_path = cache_dir / test_cid

    # Create minimal BAM-like content (not valid BAM, just for testing)
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


def create_mock_reference(cache_dir: Path, test_cid: str) -> tuple[Path, IpFile]:
    """
    Create a minimal valid reference FASTA for testing.

    Returns:
        Tuple of (ref_path, ipfile)
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    ref_path = cache_dir / test_cid

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


@pytest.mark.asyncio
async def test_baserecalibrator_creates_report():
    """Test that baserecalibrator creates a recalibration report."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12878_bqsr"
    test_cid_bam = "QmTestBAMBQSR"
    test_cid_ref = "QmTestRefBQSR"

    # Create mock files
    bam_path, bam_ipfile = create_mock_bam(
        default_client.cache_dir, sample_id, test_cid_bam
    )
    ref_path, ref_ipfile = create_mock_reference(default_client.cache_dir, test_cid_ref)

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
        recal_report = await baserecalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=["dbsnp_146.hg38.vcf.gz"],
        )

        # Verify result
        assert isinstance(recal_report, IpFile)
        assert recal_report.keyvalues.get("type") == "bqsr_report"
        assert recal_report.keyvalues.get("sample_id") == sample_id

    finally:
        # Cleanup
        if bam_path.exists():
            bam_path.unlink()
        if ref_path.exists():
            ref_path.unlink()


@pytest.mark.asyncio
async def test_baserecalibrator_rejects_empty_known_sites():
    """Test that baserecalibrator raises error for empty known_sites."""
    alignment = Alignment(
        sample_id="test",
        bam_name="test.bam",
        files=[],
    )

    ref = Reference(
        ref_name="test.fa",
        files=[],
    )

    with pytest.raises(ValueError, match="known_sites list cannot be empty"):
        await baserecalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=[],
        )


@pytest.mark.asyncio
async def test_baserecalibrator_task_is_callable():
    """Test that baserecalibrator is a callable task."""
    assert callable(baserecalibrator)
    assert "baserecalibrator" in str(baserecalibrator)


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_baserecalibrator_exported_from_package(self):
        """Test that baserecalibrator is accessible from stargazer.tasks."""
        from stargazer.tasks import baserecalibrator

        assert callable(baserecalibrator)
