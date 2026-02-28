"""
Tests for merge_bam_alignment task.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.merge_bam_alignment import merge_bam_alignment
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile
from stargazer.types.reference import ReferenceFile


@pytest.mark.asyncio
async def test_merge_bam_alignment_merges_bams(fixtures_db):
    """Test that merge_bam_alignment creates a merged BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_merge"

    aligned_bam = Alignment(
        sample_id=sample_id,
        alignment=AlignmentFile(
            path=FIXTURES_DIR / "NA12829_TP53_bwa_aligned.bam",
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": sample_id,
                "tool": "bwa_mem",
                "sorted": "unsorted",
            },
        ),
    )

    unmapped_bam = Alignment(
        sample_id=sample_id,
        alignment=AlignmentFile(
            path=FIXTURES_DIR / "NA12829_TP53_unmapped.bam",
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": sample_id,
                "tool": "picard",
                "sorted": "queryname",
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

    merged = await merge_bam_alignment(
        aligned_bam=aligned_bam,
        unmapped_bam=unmapped_bam,
        ref=ref,
    )

    assert isinstance(merged, Alignment)
    assert merged.sample_id == sample_id

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
