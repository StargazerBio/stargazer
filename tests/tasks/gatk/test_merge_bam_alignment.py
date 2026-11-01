"""
Tests for merge_bam_alignment task.
"""

import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer.assets import Alignment, Reference
from stargazer.tasks.gatk.merge_bam_alignment import merge_bam_alignment


@pytest.mark.asyncio
async def test_merge_bam_alignment_merges_bams():
    """Test that merge_bam_alignment creates a merged BAM."""
    sample_id = "NA12829_TP53_merge"

    aligned_bam = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_bwa_aligned.bam",
        sample_id=sample_id,
        tool="bwa_mem",
    )

    unmapped_bam = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_unmapped.bam",
        sample_id=sample_id,
        sorted="queryname",
        tool="picard",
    )

    ref = Reference(
        path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa",
        build="GRCh38",
    )

    merged = await merge_bam_alignment(
        aligned_bam=aligned_bam,
        unmapped_bam=unmapped_bam,
        ref=ref,
    )

    assert isinstance(merged, Alignment)
    assert merged.sample_id == sample_id
    assert merged.sorted == "coordinate"
    assert merged.tool == "gatk_merge_bam_alignment"
    assert merged.path is not None
    bam = await merged.fetch()
    assert bam.exists()
    # Downstream tools read the index from beside the BAM.
    assert (bam.parent / "NA12829_TP53_merge_merged.bai").exists()
