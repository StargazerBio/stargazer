"""Tests for the haplotype_caller task."""

from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer.assets import Alignment, AlignmentIndex, Reference, assemble
from stargazer.tasks.gatk.haplotype_caller import haplotype_caller


async def test_haplotype_caller_lists_its_sample_and_links_its_alignment():
    """The GVCF names its one sample and its alignment, before and after storage."""
    sample_id = "NA12829_TP53"
    alignment = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_recalibrated.bam",
        sample_id=sample_id,
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=True,
        tool="gatk_apply_bqsr",
    )
    await AlignmentIndex.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_recalibrated.bai",
        sample_id=sample_id,
        companion_of=alignment.cid,
    )
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

    gvcf = await haplotype_caller(alignment=alignment, ref=ref)

    (stored,) = await assemble(asset="variants", sample_id=sample_id)
    for variants in (gvcf, stored):
        assert variants.source_samples == [sample_id]
        assert variants.source_cids == [alignment.cid]
