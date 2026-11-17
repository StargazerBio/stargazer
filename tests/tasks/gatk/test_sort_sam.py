"""Tests for the sort_sam task."""

import pytest
from conftest import GATK_FIXTURES_DIR

from stargazer.assets import Alignment, assemble
from stargazer.tasks.gatk.sort_sam import sort_sam


async def test_sort_sam_sorts_and_links_its_output_to_its_input():
    """The sorted BAM is indexed beside itself and records its BAM and reference."""
    alignment = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_merged.bam",
        sample_id="NA12829_TP53_merged",
        tool="bwa_mem",
        reference_cid="bafyreference",
    )

    sorted_bam = await sort_sam(alignment=alignment, sort_order="coordinate")

    assert (sorted_bam.sample_id, sorted_bam.sorted, sorted_bam.tool) == (
        "NA12829_TP53_merged",
        "coordinate",
        "gatk_sort_sam",
    )
    assert (sorted_bam.source_cid, sorted_bam.reference_cid) == (
        alignment.cid,
        "bafyreference",
    )
    bam = await sorted_bam.fetch()
    assert (bam.parent / "NA12829_TP53_merged_sorted_coordinate.bai").exists()
    found = await assemble(asset="alignment", source_cid=alignment.cid)
    assert [a.cid for a in found] == [sorted_bam.cid]


async def test_sort_sam_validates_sort_order():
    """An unknown sort order is refused before the tool runs."""
    with pytest.raises(ValueError, match="Invalid sort_order"):
        await sort_sam(
            alignment=Alignment(sample_id="test"), sort_order="invalid_order"
        )
