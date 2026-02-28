"""
Tests for genotype_gvcf task.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.genotype_gvcf import genotype_gvcf
from stargazer.types import Reference, Variants
from stargazer.types.reference import ReferenceFile
from stargazer.types.variants import VariantsFile


@pytest.mark.asyncio
async def test_genotype_gvcf_converts_to_vcf(fixtures_db):
    """Test that genotype_gvcf converts GVCF to VCF."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_genotype"

    gvcf = Variants(
        sample_id=sample_id,
        vcf=VariantsFile(
            path=FIXTURES_DIR / "NA12829_TP53.g.vcf",
            keyvalues={
                "type": "variants",
                "component": "vcf",
                "sample_id": sample_id,
                "caller": "haplotypecaller",
                "variant_type": "gvcf",
                "build": "GRCh38",
            },
        ),
    )

    ref = Reference(
        build="GRCh38",
        fasta=ReferenceFile(
            path=FIXTURES_DIR / "GRCh38_TP53.fa",
            keyvalues={"type": "reference", "component": "fasta", "build": "GRCh38"},
        ),
    )

    fixtures_db()  # checkout: switch to isolated work dir

    result = await genotype_gvcf(gvcf=gvcf, ref=ref)

    assert isinstance(result, Variants)
    assert result.sample_id == sample_id
    assert not result.is_gvcf

    vcf_file = result.vcf
    assert vcf_file is not None
    assert vcf_file.keyvalues.get("caller") == "genotype_gvcf"
    assert vcf_file.keyvalues.get("variant_type") == "vcf"


@pytest.mark.asyncio
async def test_genotype_gvcf_rejects_vcf_input():
    """Test that genotype_gvcf raises error for VCF input (expects GVCF)."""
    sample_id = "NA12829_test"
    vcf_file = VariantsFile(
        cid="QmTestVCFInput",
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": sample_id,
            "variant_type": "vcf",
        },
    )
    with pytest.raises(ValueError, match="requires a GVCF file"):
        await genotype_gvcf(
            gvcf=Variants(sample_id=sample_id, vcf=vcf_file),
            ref=Reference(build="test"),
        )


@pytest.mark.asyncio
async def test_genotype_gvcf_empty_gvcf():
    """Test that genotype_gvcf raises error for empty GVCF."""
    with pytest.raises(ValueError, match="requires a GVCF file"):
        await genotype_gvcf(
            gvcf=Variants(sample_id="empty"), ref=Reference(build="test")
        )
