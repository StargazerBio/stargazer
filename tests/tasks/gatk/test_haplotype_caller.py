"""
Tests for haplotype_caller task.
"""

import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer.assets import Alignment, Reference, assemble
from stargazer.tasks.gatk.haplotype_caller import haplotype_caller


@pytest.mark.asyncio
async def test_haplotype_caller_lists_its_sample(fixtures_db):
    """The GVCF names its one sample in a list, before and after storage."""
    sample_id = "NA12829_TP53"

    alignment = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_recalibrated.bam",
        sample_id=sample_id,
        format="bam",
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=True,
        tool="gatk_apply_bqsr",
    )

    ref = Reference(
        path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa",
        build="GRCh38",
    )

    fixtures_db()  # checkout: switch to isolated work dir

    gvcf = await haplotype_caller(alignment=alignment, ref=ref)

    assert gvcf.source_samples == [sample_id]
    (stored,) = await assemble(asset="variants", sample_id=sample_id)
    assert stored.source_samples == [sample_id]
