"""
Tests for haplotype_caller task.
"""

import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer.assets import Alignment, AlignmentIndex, Reference, assemble
from stargazer.tasks.gatk.haplotype_caller import haplotype_caller


@pytest.mark.asyncio
async def test_haplotype_caller_lists_its_sample():
    """The GVCF names its one sample in a list, before and after storage."""
    sample_id = "NA12829_TP53"

    alignment = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_recalibrated.bam",
        sample_id=sample_id,
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=True,
        tool="gatk_apply_bqsr",
    )

    ref = Reference(
        path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa",
        build="GRCh38",
    )

    gvcf = await haplotype_caller(alignment=alignment, ref=ref)

    assert gvcf.source_samples == [sample_id]
    (stored,) = await assemble(asset="variants", sample_id=sample_id)
    assert stored.source_samples == [sample_id]


async def test_haplotype_caller_links_its_gvcf_to_its_alignment():
    """The GVCF records the alignment it was made from, before and after storage."""
    sample_id = "NA12829_TP53"

    alignment = Alignment()
    await alignment.update(
        GATK_FIXTURES_DIR / "NA12829_TP53_recalibrated.bam",
        sample_id=sample_id,
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=True,
        tool="gatk_apply_bqsr",
    )
    await AlignmentIndex().update(
        GATK_FIXTURES_DIR / "NA12829_TP53_recalibrated.bai",
        sample_id=sample_id,
        companion_of=alignment.cid,
    )

    ref = Reference(
        path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa",
        build="GRCh38",
    )

    gvcf = await haplotype_caller(alignment=alignment, ref=ref)

    assert alignment.cid != ""
    assert gvcf.source_cids == [alignment.cid]
    (stored,) = await assemble(asset="variants", sample_id=sample_id)
    assert stored.source_cids == [alignment.cid]
