"""Tests for the merge_bam_alignment task."""

from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer.assets import Alignment, Reference, assemble
from stargazer.tasks.gatk.merge_bam_alignment import merge_bam_alignment


async def test_merge_bam_alignment_merges_and_links_its_output_to_the_aligned_bam():
    """The merged BAM is sorted, indexed beside itself and records the aligned BAM."""
    sample_id = "NA12829_TP53_merge"
    aligned_bam = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_bwa_aligned.bam",
        sample_id=sample_id,
        tool="bwa_mem",
    )
    unmapped_bam = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_unmapped.bam",
        sample_id=sample_id,
        sorted="queryname",
        tool="picard",
    )
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

    merged = await merge_bam_alignment(
        aligned_bam=aligned_bam, unmapped_bam=unmapped_bam, ref=ref
    )

    assert (merged.sample_id, merged.sorted, merged.tool) == (
        sample_id,
        "coordinate",
        "gatk_merge_bam_alignment",
    )
    assert merged.source_cid == aligned_bam.cid
    bam = await merged.fetch()
    assert (bam.parent / "NA12829_TP53_merge_merged.bai").exists()
    found = await assemble(asset="alignment", source_cid=aligned_bam.cid)
    assert [a.cid for a in found] == [merged.cid]
