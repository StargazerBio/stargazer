"""
Tests for mergebamalignment task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.mergebamalignment import mergebamalignment
from stargazer.types import Reference, Alignment
from stargazer.utils.pinata import IpFile, default_client


def create_mock_bam(
    local_dir: Path, sample_id: str, test_cid: str, bam_type: str = "aligned"
) -> tuple[Path, IpFile]:
    """
    Create a minimal mock BAM file for testing.

    Args:
        bam_type: "aligned" or "unmapped"

    Returns:
        Tuple of (bam_path, ipfile)
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    bam_path = local_dir / test_cid

    # Create minimal BAM-like content
    bam_path.write_bytes(b"BAM\x01mock_bam_content")

    ipfile = IpFile(
        id=f"test-{sample_id}-{bam_type}",
        cid=test_cid,
        name=f"{sample_id}_{bam_type}.bam",
        size=bam_path.stat().st_size,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "bwa_mem" if bam_type == "aligned" else "picard",
            "sorted": "queryname" if bam_type == "unmapped" else "unsorted",
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
GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC
"""
    ref_path.write_text(ref_content)

    ipfile = IpFile(
        id="test-ref",
        cid=test_cid,
        name="test_reference.fa",
        size=ref_path.stat().st_size,
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )

    return ref_path, ipfile


@pytest.mark.asyncio
async def test_mergebamalignment_merges_bams():
    """Test that mergebamalignment creates a merged BAM."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12878_merge"
    test_cid_aligned = "QmTestBAMAligned"
    test_cid_unmapped = "QmTestBAMUnmapped"
    test_cid_ref = "QmTestRefMerge"

    # Create mock files
    aligned_path, aligned_ipfile = create_mock_bam(
        default_client.local_dir, sample_id, test_cid_aligned, "aligned"
    )
    unmapped_path, unmapped_ipfile = create_mock_bam(
        default_client.local_dir, sample_id, test_cid_unmapped, "unmapped"
    )
    ref_path, ref_ipfile = create_mock_reference(default_client.local_dir, test_cid_ref)

    aligned_bam = Alignment(
        sample_id=sample_id,
        alignment=aligned_ipfile,
    )

    unmapped_bam = Alignment(
        sample_id=sample_id,
        alignment=unmapped_ipfile,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_ipfile,
    )

    try:
        merged = await mergebamalignment(
            aligned_bam=aligned_bam,
            unmapped_bam=unmapped_bam,
            ref=ref,
        )

        # Verify result
        assert isinstance(merged, Alignment)
        assert merged.sample_id == sample_id

        # Check metadata
        bam_file = merged.alignment
        assert bam_file is not None
        assert bam_file.keyvalues.get("sorted") == "coordinate"
        assert bam_file.keyvalues.get("tool") == "gatk_mergebamalignment"

    finally:
        # Cleanup
        if aligned_path.exists():
            aligned_path.unlink()
        if unmapped_path.exists():
            unmapped_path.unlink()
        if ref_path.exists():
            ref_path.unlink()


@pytest.mark.asyncio
async def test_mergebamalignment_task_is_callable():
    """Test that mergebamalignment is a callable task."""
    assert callable(mergebamalignment)
    assert "mergebamalignment" in str(mergebamalignment)


class TestMergeBamAlignmentExports:
    """Test that mergebamalignment task is properly exported."""

    def test_mergebamalignment_exported_from_package(self):
        """Test that mergebamalignment is accessible from stargazer.tasks."""
        from stargazer.tasks import mergebamalignment

        assert callable(mergebamalignment)
