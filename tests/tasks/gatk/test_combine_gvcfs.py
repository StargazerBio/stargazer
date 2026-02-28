"""
Tests for combine_gvcfs task.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.combine_gvcfs import combine_gvcfs
from stargazer.types import Reference, Variants
from stargazer.types.reference import ReferenceFile
from stargazer.types.variants import VariantsFile

SAMPLE_GVCFS = {
    "NA12829": "NA12829_TP53.g.vcf",
    "NA12891": "NA12891_TP53.g.vcf",
    "NA12892": "NA12892_TP53.g.vcf",
}


def make_ref() -> Reference:
    return Reference(
        build="GRCh38",
        fasta=ReferenceFile(
            path=FIXTURES_DIR / "GRCh38_TP53.fa",
            keyvalues={"type": "reference", "component": "fasta", "build": "GRCh38"},
        ),
    )


def make_gvcf(sample_id: str) -> Variants:
    return Variants(
        sample_id=sample_id,
        vcf=VariantsFile(
            path=FIXTURES_DIR / SAMPLE_GVCFS[sample_id],
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


@pytest.mark.asyncio
async def test_combine_gvcfs_merges_samples(fixtures_db):
    """Test that combine_gvcfs merges multiple GVCFs."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_ids = ["NA12829", "NA12891", "NA12892"]
    gvcfs = [make_gvcf(sid) for sid in sample_ids]
    ref = make_ref()

    fixtures_db()  # checkout: switch to isolated work dir

    result = await combine_gvcfs(gvcfs=gvcfs, ref=ref, cohort_id="test_family")

    assert isinstance(result, Variants)
    assert result.sample_id == "test_family"
    assert result.is_gvcf
    assert result.is_multi_sample
    assert set(result.source_samples) == set(sample_ids)

    combined_file = result.vcf
    assert combined_file is not None
    assert combined_file.keyvalues.get("caller") == "combine_gvcfs"
    assert combined_file.keyvalues.get("sample_count") == "3"


@pytest.mark.asyncio
async def test_combine_gvcfs_rejects_empty_list():
    """Test that combine_gvcfs raises error for empty list."""
    with pytest.raises(ValueError, match="cannot be empty"):
        await combine_gvcfs(gvcfs=[], ref=Reference(build="test"))


@pytest.mark.asyncio
async def test_combine_gvcfs_rejects_vcf_input():
    """Test that combine_gvcfs raises error when any input is VCF (not GVCF)."""
    sample_id = "NA12878_vcf"
    vcf_file = VariantsFile(
        cid="QmTestVCFCombine",
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": sample_id,
            "variant_type": "vcf",
        },
    )
    with pytest.raises(ValueError, match="requires GVCF files"):
        await combine_gvcfs(
            gvcfs=[Variants(sample_id=sample_id, vcf=vcf_file)],
            ref=Reference(build="test"),
        )


@pytest.mark.asyncio
async def test_combine_gvcfs_single_sample(fixtures_db):
    """Test that combine_gvcfs works with a single sample (edge case)."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829"
    gvcf = make_gvcf(sample_id)
    ref = make_ref()

    fixtures_db()  # checkout

    result = await combine_gvcfs(
        gvcfs=[gvcf], ref=ref, cohort_id="single_sample_cohort"
    )

    assert isinstance(result, Variants)
    assert result.is_gvcf
    assert not result.is_multi_sample
    assert result.source_samples == [sample_id]


@pytest.mark.asyncio
async def test_variants_multi_sample_properties():
    """Test new multi-sample properties on Variants type."""
    single_file = VariantsFile(
        cid="QmSingle",
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": "NA12878",
            "variant_type": "gvcf",
        },
    )
    single_variant = Variants(sample_id="NA12878", vcf=single_file)
    assert not single_variant.is_multi_sample
    assert single_variant.source_samples == ["NA12878"]

    multi_file = VariantsFile(
        cid="QmMulti",
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": "cohort",
            "variant_type": "gvcf",
            "sample_count": "3",
            "source_samples": "NA12878,NA12891,NA12892",
        },
    )
    multi_variant = Variants(sample_id="cohort", vcf=multi_file)
    assert multi_variant.is_multi_sample
    assert set(multi_variant.source_samples) == {"NA12878", "NA12891", "NA12892"}
