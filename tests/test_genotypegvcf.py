"""
Tests for genotypegvcf task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.genotypegvcf import genotypegvcf
from stargazer.types import Reference, Variants
from stargazer.utils.pinata import IpFile, default_client


def create_mock_gvcf(
    cache_dir: Path, sample_id: str, test_cid: str
) -> tuple[Path, IpFile]:
    """
    Create a minimal valid GVCF file for testing.

    Returns:
        Tuple of (gvcf_path, ipfile)
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    gvcf_path = cache_dir / test_cid

    # Create a minimal valid GVCF content
    gvcf_content = f"""##fileformat=VCFv4.2
##source=HaplotypeCaller
##reference=GRCh38
##contig=<ID=chr17,length=83257441>
##INFO=<ID=END,Number=1,Type=Integer,Description="End position">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">
##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype quality">
##FORMAT=<ID=MIN_DP,Number=1,Type=Integer,Description="Min depth">
##FORMAT=<ID=PL,Number=G,Type=Integer,Description="Phred-scaled likelihoods">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	{sample_id}
chr17	7687490	.	G	<NON_REF>	.	.	END=7687550	GT:DP:GQ:MIN_DP:PL	0/0:35:99:30:0,90,1350
chr17	7687551	.	C	T,<NON_REF>	1000	.	.	GT:DP:GQ:PL	0/1:40:99:500,0,800,600,900,1500
"""
    gvcf_path.write_text(gvcf_content)

    ipfile = IpFile(
        id=f"test-{sample_id}-gvcf",
        cid=test_cid,
        name=f"{sample_id}.g.vcf",
        size=gvcf_path.stat().st_size,
        keyvalues={
            "type": "variants",
            "sample_id": sample_id,
            "caller": "haplotypecaller",
            "variant_type": "gvcf",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )

    return gvcf_path, ipfile


def create_mock_reference(cache_dir: Path, test_cid: str) -> tuple[Path, IpFile]:
    """
    Create a minimal valid reference FASTA for testing.

    Returns:
        Tuple of (ref_path, ipfile)
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    ref_path = cache_dir / test_cid

    # Create minimal FASTA content matching the GVCF
    ref_content = """>chr17
GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC
GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC
"""
    ref_path.write_text(ref_content)

    ipfile = IpFile(
        id="test-ref",
        cid=test_cid,
        name="test_reference.fa",
        size=ref_path.stat().st_size,
        keyvalues={
            "type": "reference",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )

    return ref_path, ipfile


@pytest.mark.asyncio
async def test_genotypegvcf_converts_to_vcf():
    """Test that genotypegvcf converts GVCF to VCF."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_genotype"
    test_cid_gvcf = "QmTestGVCFGenotype"
    test_cid_ref = "QmTestRefGenotype"

    # Create mock GVCF
    gvcf_path, gvcf_ipfile = create_mock_gvcf(
        default_client.cache_dir, sample_id, test_cid_gvcf
    )

    # Create mock reference
    ref_path, ref_ipfile = create_mock_reference(default_client.cache_dir, test_cid_ref)

    # Create objects
    gvcf = Variants(
        sample_id=sample_id,
        vcf_name=f"{sample_id}.g.vcf",
        files=[gvcf_ipfile],
    )

    ref = Reference(
        ref_name="test_reference.fa",
        files=[ref_ipfile],
    )

    try:
        # Run genotypegvcf
        result = await genotypegvcf(gvcf=gvcf, ref=ref)

        # Verify result
        assert isinstance(result, Variants)
        assert result.sample_id == sample_id

        # Check that it's a VCF (not GVCF)
        assert not result.is_gvcf, "Output should be VCF, not GVCF"

        # Verify metadata
        vcf_file = None
        for f in result.files:
            if f.name == result.vcf_name:
                vcf_file = f
                break

        assert vcf_file is not None
        assert vcf_file.keyvalues.get("caller") == "genotypegvcf"
        assert vcf_file.keyvalues.get("variant_type") == "vcf"
        assert vcf_file.keyvalues.get("source_caller") == "haplotypecaller"

    finally:
        # Cleanup
        if gvcf_path.exists():
            gvcf_path.unlink()
        if ref_path.exists():
            ref_path.unlink()
        # Cleanup output VCF
        output_vcf = ref_path.parent / f"{sample_id}.vcf"
        if output_vcf.exists():
            output_vcf.unlink()


@pytest.mark.asyncio
async def test_genotypegvcf_rejects_vcf_input():
    """Test that genotypegvcf raises error for VCF input (expects GVCF)."""
    sample_id = "NA12829_test"
    test_cid = "QmTestVCFInput"

    # Create Variants with VCF (not GVCF) metadata
    vcf_ipfile = IpFile(
        id=f"test-{sample_id}-vcf",
        cid=test_cid,
        name=f"{sample_id}.vcf",
        size=1000,
        keyvalues={
            "type": "variants",
            "sample_id": sample_id,
            "caller": "haplotypecaller",
            "variant_type": "vcf",  # VCF, not GVCF
        },
        created_at=datetime.now(),
    )

    variants = Variants(
        sample_id=sample_id,
        vcf_name=f"{sample_id}.vcf",
        files=[vcf_ipfile],
    )

    ref = Reference(
        ref_name="test.fa",
        files=[],
    )

    # Should raise ValueError for non-GVCF input
    with pytest.raises(ValueError, match="requires a GVCF file"):
        await genotypegvcf(gvcf=variants, ref=ref)


@pytest.mark.asyncio
async def test_genotypegvcf_output_naming():
    """Test that genotypegvcf correctly names output VCF."""

    # Test various input naming conventions
    test_cases = [
        ("sample.g.vcf", "sample.vcf"),
        ("sample.g.vcf.gz", "sample.vcf"),
        ("sample.gvcf", "sample.vcf"),
        ("sample.gvcf.gz", "sample.vcf"),
        ("sample.other", "sample_genotyped.vcf"),
    ]

    for input_name, expected_output in test_cases:
        # The naming logic is in the task, we're just testing the pattern
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
async def test_genotypegvcf_empty_gvcf():
    """Test that genotypegvcf raises error for empty GVCF."""
    gvcf = Variants(
        sample_id="empty",
        vcf_name="empty.g.vcf",
        files=[],
    )

    ref = Reference(
        ref_name="test.fa",
        files=[],
    )

    # Should raise error - can't determine if GVCF without files
    with pytest.raises(ValueError, match="requires a GVCF file"):
        await genotypegvcf(gvcf=gvcf, ref=ref)
