"""
Tests for sort_sam task.
"""

import pytest
from conftest import GATK_FIXTURES_DIR

from stargazer.assets import Alignment, assemble
from stargazer.tasks.gatk.sort_sam import sort_sam


@pytest.mark.asyncio
async def test_sort_sam_sorts_bam():
    """Test that sort_sam creates a sorted BAM."""
    sample_id = "NA12829_TP53_merged"

    alignment = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_merged.bam",
        sample_id=sample_id,
        tool="bwa_mem",
    )

    sorted_bam = await sort_sam(alignment=alignment, sort_order="coordinate")

    assert isinstance(sorted_bam, Alignment)
    assert sorted_bam.sample_id == sample_id
    assert sorted_bam.sorted == "coordinate"
    assert sorted_bam.tool == "gatk_sort_sam"
    assert sorted_bam.path is not None
    bam = await sorted_bam.fetch()
    assert bam.exists()
    # Downstream tools read the index from beside the BAM.
    assert (bam.parent / "NA12829_TP53_merged_sorted_coordinate.bai").exists()


async def test_sort_sam_links_its_output_to_its_input():
    """The sorted BAM records the BAM it was made from and its reference."""
    alignment = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_merged.bam",
        sample_id="NA12829_TP53_merged",
        tool="bwa_mem",
        reference_cid="bafyreference",
    )

    sorted_bam = await sort_sam(alignment=alignment, sort_order="coordinate")

    assert alignment.cid != ""
    assert (sorted_bam.source_cid, sorted_bam.reference_cid) == (
        alignment.cid,
        "bafyreference",
    )
    found = await assemble(asset="alignment", source_cid=alignment.cid)
    assert [a.cid for a in found] == [sorted_bam.cid]


@pytest.mark.asyncio
async def test_sort_sam_validates_sort_order():
    """Test that sort_sam rejects invalid sort orders."""
    alignment = Alignment(sample_id="test")

    with pytest.raises(ValueError, match="Invalid sort_order"):
        await sort_sam(alignment=alignment, sort_order="invalid_order")
