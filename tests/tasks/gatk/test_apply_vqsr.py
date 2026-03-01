"""
Tests for apply_vqsr task.
"""

import pytest

from stargazer.tasks.gatk.apply_vqsr import apply_vqsr
from stargazer.types import Variants
from stargazer.types.variants import VariantsFile, RecalFile, TranchesFile


def test_apply_vqsr_task_is_callable():
    assert callable(apply_vqsr)
    assert "apply_vqsr" in str(apply_vqsr)


@pytest.mark.asyncio
async def test_apply_vqsr_rejects_gvcf():
    vcf = Variants(
        sample_id="test",
        vcf=VariantsFile(keyvalues={"variant_type": "gvcf"}),
        recal=RecalFile(keyvalues={"mode": "snp"}),
        tranches=TranchesFile(keyvalues={"mode": "snp"}),
    )
    with pytest.raises(ValueError, match="GVCF"):
        await apply_vqsr(vcf=vcf)


@pytest.mark.asyncio
async def test_apply_vqsr_rejects_missing_recal():
    vcf = Variants(
        sample_id="test",
        vcf=VariantsFile(),
        tranches=TranchesFile(),
    )
    with pytest.raises(ValueError, match="vcf.recal"):
        await apply_vqsr(vcf=vcf)


@pytest.mark.asyncio
async def test_apply_vqsr_rejects_missing_tranches():
    vcf = Variants(
        sample_id="test",
        vcf=VariantsFile(),
        recal=RecalFile(keyvalues={"mode": "snp"}),
    )
    with pytest.raises(ValueError, match="vcf.tranches"):
        await apply_vqsr(vcf=vcf)
