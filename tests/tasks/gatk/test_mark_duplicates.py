"""
Tests for mark_duplicates task.
"""

import pytest
from conftest import GATK_FIXTURES_DIR

from stargazer.assets import Alignment
from stargazer.tasks.gatk.mark_duplicates import mark_duplicates


@pytest.mark.asyncio
async def test_mark_duplicates_marks_duplicates():
    """Test that mark_duplicates creates a marked BAM."""
    sample_id = "NA12829_TP53_merged"

    alignment = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_merged.bam",
        sample_id=sample_id,
        sorted="coordinate",
        tool="gatk_merge_bam_alignment",
    )

    marked = await mark_duplicates(alignment=alignment)

    assert isinstance(marked, Alignment)
    assert marked.sample_id == sample_id
    assert marked.duplicates_marked is True
    assert marked.tool == "gatk_mark_duplicates"
    assert marked.path is not None
    bam = await marked.fetch()
    assert bam.exists()
    # Downstream tools read the index from beside the BAM.
    assert (bam.parent / "NA12829_TP53_merged_marked_duplicates.bai").exists()
