"""
Tests for combine_gvcfs task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.combine_gvcfs import combine_gvcfs
from stargazer.types import Reference, Variants
from stargazer.utils.storage import default_client
from stargazer.utils.ipfile import IpFile

# Sample GVCFs available as fixtures (created from NA12829 TP53 data)
SAMPLE_GVCFS = {
    "NA12829": "NA12829_TP53.g.vcf",
    "NA12891": "NA12891_TP53.g.vcf",
    "NA12892": "NA12892_TP53.g.vcf",
}


def setup_fixture_files(local_dir: Path, sample_ids: list[str]) -> dict[str, Path]:
    """
    Copy real TP53 fixture files into the test's local directory.

    Returns dict of fixture name to local path.
    """
    local_dir.mkdir(parents=True, exist_ok=True)

    # Always copy reference files
    ref_files = {
        "ref_fasta": ("GRCh38_TP53.fa", "GRCh38_TP53.fa"),
        "ref_fai": ("GRCh38_TP53.fa.fai", "GRCh38_TP53.fa.fai"),
        "ref_dict": ("GRCh38_TP53.dict", "GRCh38_TP53.dict"),
    }

    paths = {}
    for key, (src_name, dst_name) in ref_files.items():
        src = FIXTURES_DIR / src_name
        dst = local_dir / dst_name
        shutil.copy2(src, dst)
        paths[key] = dst

    # Copy requested sample GVCFs
    for sample_id in sample_ids:
        gvcf_name = SAMPLE_GVCFS[sample_id]
        src = FIXTURES_DIR / gvcf_name
        dst = local_dir / gvcf_name
        shutil.copy2(src, dst)
        paths[f"gvcf_{sample_id}"] = dst

    return paths


def make_ref(paths: dict[str, Path]) -> Reference:
    """Create a Reference object from fixture paths."""
    ref_ipfile = IpFile(
        id="test-ref-fasta",
        cid="test_ref_fasta",
        name="GRCh38_TP53.fa",
        size=paths["ref_fasta"].stat().st_size,
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )
    ref_ipfile.local_path = paths["ref_fasta"]
    return Reference(build="GRCh38", fasta=ref_ipfile)


def make_gvcf(sample_id: str, paths: dict[str, Path]) -> Variants:
    """Create a Variants GVCF object from fixture paths."""
    gvcf_name = SAMPLE_GVCFS[sample_id]
    gvcf_path = paths[f"gvcf_{sample_id}"]
    gvcf_ipfile = IpFile(
        id=f"test-{sample_id}-gvcf",
        cid=f"test_gvcf_{sample_id}",
        name=gvcf_name,
        size=gvcf_path.stat().st_size,
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": sample_id,
            "caller": "haplotypecaller",
            "variant_type": "gvcf",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )
    gvcf_ipfile.local_path = gvcf_path
    return Variants(sample_id=sample_id, vcf=gvcf_ipfile)


@pytest.mark.asyncio
async def test_combine_gvcfs_merges_samples():
    """Test that combine_gvcfs merges multiple GVCFs."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_ids = ["NA12829", "NA12891", "NA12892"]
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir, sample_ids)

    ref = make_ref(paths)
    gvcfs = [make_gvcf(sid, paths) for sid in sample_ids]

    result = await combine_gvcfs(
        gvcfs=gvcfs,
        ref=ref,
        cohort_id="test_family",
    )

    # Verify result
    assert isinstance(result, Variants)
    assert result.sample_id == "test_family"

    # Check that it's still a GVCF
    assert result.is_gvcf, "Combined output should be GVCF"

    # Verify it's marked as multi-sample
    assert result.is_multi_sample, "Combined GVCF should be multi-sample"

    # Verify source samples are tracked
    assert set(result.source_samples) == set(sample_ids)

    # Verify metadata
    combined_file = result.vcf
    assert combined_file is not None
    assert combined_file.keyvalues.get("caller") == "combine_gvcfs"
    assert combined_file.keyvalues.get("sample_count") == "3"


@pytest.mark.asyncio
async def test_combine_gvcfs_rejects_empty_list():
    """Test that combine_gvcfs raises error for empty list."""
    ref = Reference(build="test")

    with pytest.raises(ValueError, match="cannot be empty"):
        await combine_gvcfs(gvcfs=[], ref=ref)


@pytest.mark.asyncio
async def test_combine_gvcfs_rejects_vcf_input():
    """Test that combine_gvcfs raises error when any input is VCF (not GVCF)."""
    sample_id = "NA12878_vcf"
    test_cid = "QmTestVCFCombine"

    vcf_ipfile = IpFile(
        id=f"test-{sample_id}-vcf",
        cid=test_cid,
        name=f"{sample_id}.vcf",
        size=1000,
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": sample_id,
            "caller": "haplotypecaller",
            "variant_type": "vcf",
        },
        created_at=datetime.now(),
    )

    variants = Variants(sample_id=sample_id, vcf=vcf_ipfile)
    ref = Reference(build="test")

    with pytest.raises(ValueError, match="requires GVCF files"):
        await combine_gvcfs(gvcfs=[variants], ref=ref)


@pytest.mark.asyncio
async def test_combine_gvcfs_single_sample():
    """Test that combine_gvcfs works with a single sample (edge case)."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir, [sample_id])

    ref = make_ref(paths)
    gvcf = make_gvcf(sample_id, paths)

    result = await combine_gvcfs(
        gvcfs=[gvcf],
        ref=ref,
        cohort_id="single_sample_cohort",
    )

    # Verify result
    assert isinstance(result, Variants)
    assert result.is_gvcf

    # Single sample should not be marked as multi-sample
    assert not result.is_multi_sample

    # Source samples should contain just the one sample
    assert result.source_samples == [sample_id]


@pytest.mark.asyncio
async def test_variants_multi_sample_properties():
    """Test new multi-sample properties on Variants type."""
    # Test single sample variant
    single_ipfile = IpFile(
        id="test-single",
        cid="QmSingle",
        name="single.g.vcf",
        size=1000,
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": "NA12878",
            "variant_type": "gvcf",
        },
        created_at=datetime.now(),
    )

    single_variant = Variants(sample_id="NA12878", vcf=single_ipfile)

    assert not single_variant.is_multi_sample
    assert single_variant.source_samples == ["NA12878"]

    # Test multi-sample variant
    multi_ipfile = IpFile(
        id="test-multi",
        cid="QmMulti",
        name="cohort.g.vcf",
        size=5000,
        keyvalues={
            "type": "variants",
            "component": "vcf",
            "sample_id": "cohort",
            "variant_type": "gvcf",
            "sample_count": "3",
            "source_samples": "NA12878,NA12891,NA12892",
        },
        created_at=datetime.now(),
    )

    multi_variant = Variants(sample_id="cohort", vcf=multi_ipfile)

    assert multi_variant.is_multi_sample
    assert set(multi_variant.source_samples) == {"NA12878", "NA12891", "NA12892"}
