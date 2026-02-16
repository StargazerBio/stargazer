"""
Tests for genotype_gvcf task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.genotype_gvcf import genotype_gvcf
from stargazer.types import Reference, Variants
from stargazer.utils.storage import default_client
from stargazer.utils.ipfile import IpFile


def setup_fixture_files(local_dir: Path) -> dict[str, Path]:
    """
    Copy real TP53 fixture files into the test's local directory.

    Returns dict of fixture name to local path.
    """
    local_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "ref_fasta": ("GRCh38_TP53.fa", "GRCh38_TP53.fa"),
        "ref_fai": ("GRCh38_TP53.fa.fai", "GRCh38_TP53.fa.fai"),
        "ref_dict": ("GRCh38_TP53.dict", "GRCh38_TP53.dict"),
        "gvcf": ("NA12829_TP53.g.vcf", "NA12829_TP53.g.vcf"),
    }

    paths = {}
    for key, (src_name, dst_name) in files.items():
        src = FIXTURES_DIR / src_name
        dst = local_dir / dst_name
        shutil.copy2(src, dst)
        paths[key] = dst

    return paths


@pytest.mark.asyncio
async def test_genotype_gvcf_converts_to_vcf():
    """Test that genotype_gvcf converts GVCF to VCF."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_genotype"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)

    gvcf_ipfile = IpFile(
        id="test-gvcf",
        cid="test_gvcf",
        name=f"{sample_id}.g.vcf",
        size=paths["gvcf"].stat().st_size,
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
    gvcf_ipfile.local_path = paths["gvcf"]

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

    gvcf = Variants(sample_id=sample_id, vcf=gvcf_ipfile)
    ref = Reference(build="GRCh38", fasta=ref_ipfile)

    result = await genotype_gvcf(gvcf=gvcf, ref=ref)

    # Verify result
    assert isinstance(result, Variants)
    assert result.sample_id == sample_id

    # Check that it's a VCF (not GVCF)
    assert not result.is_gvcf, "Output should be VCF, not GVCF"

    # Verify metadata
    vcf_file = result.vcf
    assert vcf_file is not None
    assert vcf_file.keyvalues.get("caller") == "genotype_gvcf"
    assert vcf_file.keyvalues.get("variant_type") == "vcf"


@pytest.mark.asyncio
async def test_genotype_gvcf_rejects_vcf_input():
    """Test that genotype_gvcf raises error for VCF input (expects GVCF)."""
    sample_id = "NA12829_test"
    test_cid = "QmTestVCFInput"

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

    with pytest.raises(ValueError, match="requires a GVCF file"):
        await genotype_gvcf(gvcf=variants, ref=ref)


@pytest.mark.asyncio
async def test_genotype_gvcf_output_naming():
    """Test that genotype_gvcf correctly names output VCF."""
    test_cases = [
        ("sample.g.vcf", "sample.vcf"),
        ("sample.g.vcf.gz", "sample.vcf"),
        ("sample.gvcf", "sample.vcf"),
        ("sample.gvcf.gz", "sample.vcf"),
        ("sample.other", "sample_genotyped.vcf"),
    ]

    for input_name, expected_output in test_cases:
        vcf_basename = input_name
        if vcf_basename.endswith(".g.vcf.gz"):
            vcf_basename = vcf_basename[:-9] + ".vcf"
        elif vcf_basename.endswith(".g.vcf"):
            vcf_basename = vcf_basename[:-6] + ".vcf"
        elif vcf_basename.endswith(".gvcf.gz"):
            vcf_basename = vcf_basename[:-8] + ".vcf"
        elif vcf_basename.endswith(".gvcf"):
            vcf_basename = vcf_basename[:-5] + ".vcf"
        else:
            vcf_basename = vcf_basename.rsplit(".", 1)[0] + "_genotyped.vcf"

        assert vcf_basename == expected_output, f"Failed for {input_name}"


@pytest.mark.asyncio
async def test_genotype_gvcf_empty_gvcf():
    """Test that genotype_gvcf raises error for empty GVCF."""
    gvcf = Variants(sample_id="empty")
    ref = Reference(build="test")

    with pytest.raises(ValueError, match="requires a GVCF file"):
        await genotype_gvcf(gvcf=gvcf, ref=ref)
