"""
Tests for sortsam task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.sortsam import sortsam
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
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "bwa_mem",
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

    # Create minimal FASTA content
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
async def test_sortsam_sorts_bam():
    """Test that sortsam creates a sorted BAM."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12878_sort"
    test_cid_bam = "QmTestBAMSort"
    test_cid_ref = "QmTestRefSort"

    # Create mock files
    bam_path, bam_ipfile = create_mock_bam(
        default_client.local_dir, sample_id, test_cid_bam
    )
    ref_path, ref_ipfile = create_mock_reference(default_client.local_dir, test_cid_ref)

    alignment = Alignment(
        sample_id=sample_id,
        alignment=bam_ipfile,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_ipfile,
    )

    try:
        sorted_bam = await sortsam(
            alignment=alignment,
            ref=ref,
            sort_order="coordinate",
        )

        # Verify result
        assert isinstance(sorted_bam, Alignment)
        assert sorted_bam.sample_id == sample_id

        # Check metadata
        bam_file = sorted_bam.alignment
        assert bam_file is not None
        assert bam_file.keyvalues.get("sorted") == "coordinate"
        assert bam_file.keyvalues.get("tool") == "gatk_sortsam"

    finally:
        # Cleanup
        if bam_path.exists():
            bam_path.unlink()
        if ref_path.exists():
            ref_path.unlink()


@pytest.mark.asyncio
async def test_sortsam_validates_sort_order():
    """Test that sortsam rejects invalid sort orders."""
    alignment = Alignment(
        sample_id="test",
    )

    ref = Reference(
        build="test",
    )

    with pytest.raises(ValueError, match="Invalid sort_order"):
        await sortsam(
            alignment=alignment,
            ref=ref,
            sort_order="invalid_order",
        )


@pytest.mark.asyncio
async def test_sortsam_task_is_callable():
    """Test that sortsam is a callable task."""
    assert callable(sortsam)
    assert "sortsam" in str(sortsam)


class TestSortSamExports:
    """Test that sortsam task is properly exported."""

    def test_sortsam_exported_from_package(self):
        """Test that sortsam is accessible from stargazer.tasks."""
        from stargazer.tasks import sortsam

        assert callable(sortsam)
