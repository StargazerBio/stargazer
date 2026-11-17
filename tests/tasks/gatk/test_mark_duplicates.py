"""Tests for the mark_duplicates task."""

from conftest import GATK_FIXTURES_DIR

from stargazer.assets import Alignment, assemble
from stargazer.tasks.gatk.mark_duplicates import mark_duplicates


async def test_mark_duplicates_marks_and_links_its_output_to_its_input():
    """The marked BAM is indexed beside itself and records its BAM and reference."""
    alignment = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_merged.bam",
        sample_id="NA12829_TP53_merged",
        sorted="coordinate",
        tool="gatk_merge_bam_alignment",
        reference_cid="bafyreference",
    )

    marked = await mark_duplicates(alignment=alignment)

    assert (marked.sample_id, marked.duplicates_marked, marked.tool) == (
        "NA12829_TP53_merged",
        True,
        "gatk_mark_duplicates",
    )
    assert (marked.source_cid, marked.reference_cid) == (
        alignment.cid,
        "bafyreference",
    )
    bam = await marked.fetch()
    assert (bam.parent / "NA12829_TP53_merged_marked_duplicates.bai").exists()
    found = await assemble(asset="alignment", source_cid=alignment.cid)
    assert [a.cid for a in found] == [marked.cid]
