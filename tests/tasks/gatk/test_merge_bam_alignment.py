"""
Tests for merge_bam_alignment task.
"""

import shutil
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.merge_bam_alignment import merge_bam_alignment
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile
from stargazer.types.reference import ReferenceFile
from stargazer.utils.storage import default_client


def setup_fixture_files(local_dir: Path) -> dict[str, Path]:
    """
    Copy real TP53 fixture files into the test's local directory.

    Returns dict of fixture name to local path.
    """
    local_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "ref_fasta": ("GRCh38_TP53.fa", "GRCh38_TP53.fa"),
        "ref_fai": ("GRCh38_TP53.fa.fai", "GRCh38_TP53.fa.fai"),
        "ref_dict": ("GRCh38_TP53.dict", "GRCh38_TP53.dict"),
        "aligned_bam": ("NA12829_TP53_bwa_aligned.bam", "NA12829_TP53_bwa_aligned.bam"),
        "unmapped_bam": ("NA12829_TP53_unmapped.bam", "NA12829_TP53_unmapped.bam"),
    }

    paths = {}
    for key, (src_name, dst_name) in files.items():
        src = FIXTURES_DIR / src_name
        dst = local_dir / dst_name
        shutil.copy2(src, dst)
        paths[key] = dst

    return paths


@pytest.mark.asyncio
async def test_merge_bam_alignment_merges_bams():
    """Test that merge_bam_alignment creates a merged BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_merge"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)

    # Create ComponentFile objects with path set so fetch() short-circuits
    aligned_file = AlignmentFile(
        cid="test_aligned_bam",
        path=paths["aligned_bam"],
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "bwa_mem",
            "sorted": "unsorted",
        },
    )

    unmapped_file = AlignmentFile(
        cid="test_unmapped_bam",
        path=paths["unmapped_bam"],
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "picard",
            "sorted": "queryname",
        },
    )

    ref_fasta = ReferenceFile(
        cid="test_ref_fasta",
        path=paths["ref_fasta"],
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
    )

    aligned_bam = Alignment(
        sample_id=sample_id,
        alignment=aligned_file,
    )

    unmapped_bam = Alignment(
        sample_id=sample_id,
        alignment=unmapped_file,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_fasta,
    )

    merged = await merge_bam_alignment(
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
    assert bam_file.keyvalues.get("tool") == "gatk_merge_bam_alignment"


@pytest.mark.asyncio
async def test_merge_bam_alignment_task_is_callable():
    """Test that merge_bam_alignment is a callable task."""
    assert callable(merge_bam_alignment)
    assert "merge_bam_alignment" in str(merge_bam_alignment)


class TestMergeBamAlignmentExports:
    """Test that merge_bam_alignment task is properly exported."""

    def test_merge_bam_alignment_exported_from_package(self):
        """Test that merge_bam_alignment is accessible from stargazer.tasks."""
        from stargazer.tasks import merge_bam_alignment

        assert callable(merge_bam_alignment)
