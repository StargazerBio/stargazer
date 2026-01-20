"""
Tests for baserecalibrator task.
"""

import shutil
from pathlib import Path

import pytest

from stargazer.tasks import hydrate
from stargazer.tasks.gatk.baserecalibrator import baserecalibrator
from stargazer.types import Reference, Alignment
from stargazer.utils.pinata import default_client, IpFile


async def create_mock_bam(local_dir: Path, sample_id: str) -> Path:
    """
    Create a minimal mock BAM file for testing and upload it.

    Returns:
        Path to the created BAM file
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    bam_path = local_dir / f"{sample_id}.bam"

    # Create minimal BAM-like content (not valid BAM, just for testing)
    bam_path.write_bytes(b"BAM\x01mock_bam_content")

    await default_client.upload_file(
        bam_path,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "fq2bam",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
    )

    return bam_path


async def create_mock_reference(local_dir: Path) -> Path:
    """
    Create a minimal valid reference FASTA for testing and upload it.

    Returns:
        Path to the created reference file
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    ref_path = local_dir / "test_reference.fa"

    ref_content = """>chr17
GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC
"""
    ref_path.write_text(ref_content)

    await default_client.upload_file(
        ref_path,
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
    )

    return ref_path


@pytest.mark.asyncio
async def test_baserecalibrator_creates_report():
    """Test that baserecalibrator creates a recalibration report."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12878_bqsr"

    # Create mock files using upload/hydrate pattern
    await create_mock_bam(default_client.local_dir, sample_id)
    await create_mock_reference(default_client.local_dir)

    # Create mock known sites VCF files
    known_sites_vcf = default_client.local_dir / "dbsnp_146.hg38.vcf.gz"
    known_sites_vcf.write_bytes(b"\x1f\x8b")  # gzip magic bytes
    await default_client.upload_file(
        known_sites_vcf,
        keyvalues={"type": "known_sites", "name": "dbsnp_146.hg38.vcf.gz"},
    )

    # Use hydrate to get populated types
    from stargazer.types import Alignment as AlignmentType
    from stargazer.types import Reference as ReferenceType

    alignments = await hydrate({"type": "alignment", "sample_id": sample_id})
    alignment = next((a for a in alignments if isinstance(a, AlignmentType)), None)
    assert alignment is not None, "Alignment not found after hydrate"

    refs = await hydrate({"type": "reference", "build": "GRCh38"})
    ref = next((r for r in refs if isinstance(r, ReferenceType)), None)
    assert ref is not None, "Reference not found after hydrate"

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
        pass


@pytest.mark.asyncio
async def test_baserecalibrator_rejects_empty_known_sites():
    """Test that baserecalibrator raises error for empty known_sites."""
    alignment = Alignment(sample_id="test")

    ref = Reference(build="test")

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
