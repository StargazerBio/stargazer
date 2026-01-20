"""
Tests for markduplicates task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.markduplicates import markduplicates
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
            "tool": "sortsam",
            "sorted": "coordinate",
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


@pytest.mark.asyncio
async def test_markduplicates_marks_duplicates():
    """Test that markduplicates creates a marked BAM."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12878_markdup"
    test_cid_bam = "QmTestBAMMarkDup"
    test_cid_ref = "QmTestRefMarkDup"

    # Create mock files
    bam_path, bam_ipfile = create_mock_bam(
        default_client.local_dir, sample_id, test_cid_bam
    )
    ref_path, ref_ipfile = create_mock_reference(default_client.local_dir, test_cid_ref)

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
        marked = await markduplicates(
            alignment=alignment,
            ref=ref,
        )

        # Verify result
        assert isinstance(marked, Alignment)
        assert marked.sample_id == sample_id

        # Check metadata
        bam_file = None
        for f in marked.files:
            if f.name == marked.bam_name:
                bam_file = f
                break

        assert bam_file is not None
        assert bam_file.keyvalues.get("duplicates_marked") == "true"
        assert bam_file.keyvalues.get("tool") == "gatk_markduplicates"

    finally:
        # Cleanup
        if bam_path.exists():
            bam_path.unlink()
        if ref_path.exists():
            ref_path.unlink()


@pytest.mark.asyncio
async def test_markduplicates_task_is_callable():
    """Test that markduplicates is a callable task."""
    assert callable(markduplicates)
    assert "markduplicates" in str(markduplicates)


class TestMarkDuplicatesExports:
    """Test that markduplicates task is properly exported."""

    def test_markduplicates_exported_from_package(self):
        """Test that markduplicates is accessible from stargazer.tasks."""
        from stargazer.tasks import markduplicates

        assert callable(markduplicates)
