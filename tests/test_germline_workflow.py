"""
Integration tests for the GATK Best Practices Germline Short Variant Discovery workflow.

These tests validate the complete workflow from raw reads to final VCF.
"""

import shutil
from datetime import datetime

import pytest
from config import TEST_ROOT

from stargazer.workflows.germline_short_variant_discovery import (
    germline_single_sample,
    germline_cohort,
    germline_from_gvcfs,
)
from stargazer.types import Reference, Alignment, Variants
from stargazer.utils.pinata import IpFile, default_client


# Test fixtures
@pytest.fixture
def mock_reference():
    """Create a mock reference for testing."""
    test_cid = "QmTestRefWorkflow"
    ref_fixture = TEST_ROOT / "fixtures" / "GRCh38_TP53.fa"

    if not ref_fixture.exists():
        pytest.skip(f"Test fixture not found: {ref_fixture}")

    # Copy to cache
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_ref = default_client.local_dir / test_cid
    shutil.copy(ref_fixture, cached_ref)

    ref_ipfile = IpFile(
        id="test-ref",
        cid=test_cid,
        name="GRCh38_TP53.fa",
        size=cached_ref.stat().st_size,
        keyvalues={
            "type": "reference",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )

    ref = Reference(
        ref_name="GRCh38_TP53.fa",
        files=[ref_ipfile],
    )

    yield ref

    # Cleanup
    if cached_ref.exists():
        cached_ref.unlink()


@pytest.fixture
def mock_alignment():
    """Create a mock alignment for testing."""
    sample_id = "NA12829"
    test_cid_bam = "QmTestBAMWorkflow"
    test_cid_bai = "QmTestBAIWorkflow"

    bam_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam"
    bai_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam.bai"

    if not bam_fixture.exists():
        pytest.skip(f"Test fixture not found: {bam_fixture}")

    # Copy to cache
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.local_dir / test_cid_bam
    cached_bai = default_client.local_dir / test_cid_bai
    shutil.copy(bam_fixture, cached_bam)
    shutil.copy(bai_fixture, cached_bai)

    bam_ipfile = IpFile(
        id="test-bam",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={
            "type": "alignment",
            "sample_id": sample_id,
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
        created_at=datetime.now(),
    )

    bai_ipfile = IpFile(
        id="test-bai",
        cid=test_cid_bai,
        name="NA12829_TP53_paired.bam.bai",
        size=cached_bai.stat().st_size,
        keyvalues={
            "type": "alignment",
            "sample_id": sample_id,
        },
        created_at=datetime.now(),
    )

    alignment = Alignment(
        sample_id=sample_id,
        bam_name="NA12829_TP53_paired.bam",
        files=[bam_ipfile, bai_ipfile],
    )

    yield alignment

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()
    if cached_bai.exists():
        cached_bai.unlink()


def create_mock_gvcf(sample_id: str, test_cid: str) -> Variants:
    """Helper to create a mock GVCF for testing."""
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    gvcf_path = default_client.local_dir / test_cid

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

    gvcf_ipfile = IpFile(
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

    return Variants(
        sample_id=sample_id,
        vcf_name=f"{sample_id}.g.vcf",
        files=[gvcf_ipfile],
    )


class TestWorkflowComponents:
    """Test individual workflow components."""

    @pytest.mark.asyncio
    async def test_prepare_reference_indexes(self, mock_reference):
        """Test that prepare_reference creates necessary indices."""
        # Skip if tools not available
        if shutil.which("samtools") is None:
            pytest.skip("samtools not available")
        if shutil.which("bwa") is None:
            pytest.skip("bwa not available")

        # Note: prepare_reference uses pinata_hydrate which requires network
        # For unit testing, we test the underlying tasks directly
        from stargazer.tasks import samtools_faidx, bwa_index

        # Test samtools faidx
        ref = await samtools_faidx(mock_reference)
        assert any(f.name.endswith(".fai") for f in ref.files)

        # Test bwa index
        ref = await bwa_index(ref)
        assert any(f.name.endswith(".bwt") for f in ref.files)
        assert any(f.name.endswith(".sa") for f in ref.files)

    @pytest.mark.asyncio
    async def test_call_variants_gvcf(self, mock_alignment, mock_reference):
        """Test HaplotypeCaller in GVCF mode."""
        if shutil.which("pbrun") is None:
            pytest.skip("pbrun not available")

        from stargazer.tasks import haplotypecaller

        gvcf = await haplotypecaller(
            alignment=mock_alignment,
            ref=mock_reference,
            output_gvcf=True,
        )

        assert gvcf.is_gvcf
        assert gvcf.sample_id == mock_alignment.sample_id
        assert gvcf.caller == "haplotypecaller"


class TestSingleSampleWorkflow:
    """Test single-sample germline workflow."""

    @pytest.mark.asyncio
    async def test_single_sample_workflow_structure(self):
        """Test that single-sample workflow is a callable Flyte task."""
        # Verify it's callable (Flyte task)
        assert callable(germline_single_sample)
        # Verify it has the expected name
        assert "germline_single_sample" in str(germline_single_sample)

    @pytest.mark.asyncio
    async def test_single_sample_returns_alignment_and_vcf(self):
        """Test that single-sample workflow returns proper types."""
        # This would require full Pinata integration
        # Mark as integration test that requires external resources
        pytest.skip("Integration test requires Pinata connection")


class TestCohortWorkflow:
    """Test cohort (multi-sample) germline workflow."""

    @pytest.mark.asyncio
    async def test_cohort_workflow_structure(self):
        """Test that cohort workflow is a callable Flyte task."""
        # Verify it's callable (Flyte task)
        assert callable(germline_cohort)
        # Verify it has the expected name
        assert "germline_cohort" in str(germline_cohort)

    @pytest.mark.asyncio
    async def test_cohort_workflow_rejects_empty_samples(self):
        """Test that cohort workflow raises error for empty sample list."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await germline_cohort(
                sample_ids=[],
                ref_name="GRCh38.fa",
            )


class TestFromGVCFsWorkflow:
    """Test workflow for joint genotyping from existing GVCFs."""

    @pytest.mark.asyncio
    async def test_from_gvcfs_workflow_structure(self):
        """Test that from_gvcfs workflow is a callable Flyte task."""
        # Verify it's callable (Flyte task)
        assert callable(germline_from_gvcfs)
        # Verify it has the expected name
        assert "germline_from_gvcfs" in str(germline_from_gvcfs)

    @pytest.mark.asyncio
    async def test_from_gvcfs_rejects_empty_list(self):
        """Test that from_gvcfs workflow raises error for empty GVCF list."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await germline_from_gvcfs(
                gvcfs=[],
                ref_name="GRCh38.fa",
            )


class TestWorkflowIntegration:
    """Integration tests that test the full workflow."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_single_sample_pipeline(self):
        """
        Full integration test for single-sample pipeline.

        This test requires:
        - Pinata connection
        - GPU resources (pbrun)
        - Reference data uploaded to Pinata
        - Sample FASTQ data uploaded to Pinata
        """
        pytest.skip(
            "Full integration test - requires Pinata, GPU, and test data. "
            "Run manually with: pytest -m integration"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_cohort_pipeline(self):
        """
        Full integration test for cohort pipeline.

        This test requires:
        - Pinata connection
        - GPU resources (pbrun)
        - Reference data uploaded to Pinata
        - Multiple sample FASTQ data uploaded to Pinata
        """
        pytest.skip(
            "Full integration test - requires Pinata, GPU, and test data. "
            "Run manually with: pytest -m integration"
        )


class TestWorkflowExports:
    """Test that all workflow functions are properly exported."""

    def test_workflows_exported_from_package(self):
        """Test that workflows are accessible from stargazer.workflows."""
        from stargazer.workflows import (
            wgs_germline_snv,
            prepare_reference,
            align_sample,
            call_variants_gvcf,
            germline_single_sample,
            germline_cohort,
            germline_from_gvcfs,
        )

        # Verify they're callable
        assert callable(wgs_germline_snv)
        assert callable(prepare_reference)
        assert callable(align_sample)
        assert callable(call_variants_gvcf)
        assert callable(germline_single_sample)
        assert callable(germline_cohort)
        assert callable(germline_from_gvcfs)

    def test_tasks_exported_from_package(self):
        """Test that new tasks are accessible from stargazer.tasks."""
        from stargazer.tasks import (
            indexgvcf,
            genotypegvcf,
            combinegvcfs,
        )

        # Verify they're callable
        assert callable(indexgvcf)
        assert callable(genotypegvcf)
        assert callable(combinegvcfs)
