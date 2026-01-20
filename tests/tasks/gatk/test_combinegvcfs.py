"""
Tests for combinegvcfs task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.combinegvcfs import combinegvcfs
from stargazer.types import Reference, Variants
from stargazer.utils.pinata import IpFile, default_client


def create_mock_gvcf(
    local_dir: Path, sample_id: str, test_cid: str
) -> tuple[Path, IpFile]:
    """
    Create a minimal valid GVCF file for testing.

    Returns:
        Tuple of (gvcf_path, ipfile)
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    gvcf_path = local_dir / test_cid

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
            "component": "vcf",
            "sample_id": sample_id,
            "caller": "haplotypecaller",
            "variant_type": "gvcf",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )

    return gvcf_path, ipfile


def create_mock_reference(local_dir: Path, test_cid: str) -> tuple[Path, IpFile]:
    """
    Create a minimal valid reference FASTA for testing.

    Returns:
        Tuple of (ref_path, ipfile)
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    ref_path = local_dir / test_cid

    # Create minimal FASTA content
    ref_content = """>chr17
GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC
GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC
"""
    ref_path.write_text(ref_content)

    ipfile = IpFile(
        id="test-ref",
        cid=test_cid,
        name="test_reference.fa",
        size=ref_path.stat().st_size,
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )

    return ref_path, ipfile


@pytest.mark.asyncio
async def test_combinegvcfs_merges_samples():
    """Test that combinegvcfs merges multiple GVCFs."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_ids = ["NA12878", "NA12891", "NA12892"]
    test_cid_ref = "QmTestRefCombine"

    # Create mock reference
    ref_path, ref_ipfile = create_mock_reference(default_client.local_dir, test_cid_ref)

    ref = Reference(
        build="GRCh38",
        fasta=ref_ipfile,
    )

    # Create mock GVCFs for each sample
    gvcf_paths = []
    gvcfs = []
    for i, sample_id in enumerate(sample_ids):
        test_cid = f"QmTestGVCFCombine{i}"
        gvcf_path, gvcf_ipfile = create_mock_gvcf(
            default_client.local_dir, sample_id, test_cid
        )
        gvcf_paths.append(gvcf_path)

        gvcf = Variants(
            sample_id=sample_id,
            vcf=gvcf_ipfile,
        )
        gvcfs.append(gvcf)

    try:
        # Run combinegvcfs
        result = await combinegvcfs(
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
        assert combined_file.keyvalues.get("caller") == "combinegvcfs"
        assert combined_file.keyvalues.get("sample_count") == "3"

    finally:
        # Cleanup
        for gvcf_path in gvcf_paths:
            if gvcf_path.exists():
                gvcf_path.unlink()
        if ref_path.exists():
            ref_path.unlink()
        # Cleanup output
        output_gvcf = ref_path.parent / "test_family_combined.g.vcf"
        if output_gvcf.exists():
            output_gvcf.unlink()


@pytest.mark.asyncio
async def test_combinegvcfs_rejects_empty_list():
    """Test that combinegvcfs raises error for empty list."""
    ref = Reference(
        build="test",
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        await combinegvcfs(gvcfs=[], ref=ref)


@pytest.mark.asyncio
async def test_combinegvcfs_rejects_vcf_input():
    """Test that combinegvcfs raises error when any input is VCF (not GVCF)."""
    sample_id = "NA12878_vcf"
    test_cid = "QmTestVCFCombine"

    # Create Variants with VCF (not GVCF) metadata
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
            "variant_type": "vcf",  # VCF, not GVCF
        },
        created_at=datetime.now(),
    )

    variants = Variants(
        sample_id=sample_id,
        vcf=vcf_ipfile,
    )

    ref = Reference(
        build="test",
    )

    # Should raise ValueError for non-GVCF input
    with pytest.raises(ValueError, match="requires GVCF files"):
        await combinegvcfs(gvcfs=[variants], ref=ref)


@pytest.mark.asyncio
async def test_combinegvcfs_single_sample():
    """Test that combinegvcfs works with a single sample (edge case)."""
    # Check if gatk is available (skip if not)
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12878_single"
    test_cid_gvcf = "QmTestGVCFSingle"
    test_cid_ref = "QmTestRefSingle"

    # Create mock GVCF
    gvcf_path, gvcf_ipfile = create_mock_gvcf(
        default_client.local_dir, sample_id, test_cid_gvcf
    )

    # Create mock reference
    ref_path, ref_ipfile = create_mock_reference(default_client.local_dir, test_cid_ref)

    gvcf = Variants(
        sample_id=sample_id,
        vcf=gvcf_ipfile,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_ipfile,
    )

    try:
        # Run combinegvcfs with single sample
        result = await combinegvcfs(
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

    finally:
        # Cleanup
        if gvcf_path.exists():
            gvcf_path.unlink()
        if ref_path.exists():
            ref_path.unlink()
        output_gvcf = ref_path.parent / "single_sample_cohort_combined.g.vcf"
        if output_gvcf.exists():
            output_gvcf.unlink()


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

    single_variant = Variants(
        sample_id="NA12878",
        vcf=single_ipfile,
    )

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

    multi_variant = Variants(
        sample_id="cohort",
        vcf=multi_ipfile,
    )

    assert multi_variant.is_multi_sample
    assert set(multi_variant.source_samples) == {"NA12878", "NA12891", "NA12892"}
