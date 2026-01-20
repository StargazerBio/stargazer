"""
GATK Best Practices: Germline Short Variant Discovery (SNPs + Indels)

This workflow implements the complete GATK Best Practices pipeline for identifying
germline short variants (SNPs and Indels) from sequencing data.

The workflow supports both single-sample and multi-sample (cohort) analysis:

Single-Sample Mode:
    1. Pre-process reads (align, mark duplicates, optional BQSR)
    2. Call variants per sample (HaplotypeCaller in GVCF mode)
    3. Genotype single sample (GenotypeGVCFs)

Multi-Sample (Cohort) Mode:
    1. Pre-process reads for each sample (align, mark duplicates, optional BQSR)
    2. Call variants per sample (HaplotypeCaller in GVCF mode)
    3. Consolidate GVCFs (CombineGVCFs)
    4. Joint genotyping (GenotypeGVCFs)

References:
    - https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
    - https://gatk.broadinstitute.org/hc/en-us/articles/360035535912-Data-pre-processing-for-variant-discovery
    - https://github.com/gatk-workflows/gatk4-germline-snps-indels
"""

import asyncio

import flyte

from stargazer.config import gatk_env
from stargazer.types import Reference, Reads, Alignment, Variants
from stargazer.tasks import (
    hydrate,
    samtools_faidx,
    bwa_index,
    fq2bam,
    haplotypecaller,
    genotypegvcf,
    combinegvcfs,
    baserecalibrator,
    applybqsr,
    variantrecalibrator,
    VQSRResource,
    applyvqsr,
)


@gatk_env.task
async def prepare_reference(ref_name: str) -> Reference:
    """
    Prepare reference genome for variant calling.

    Hydrates reference from Pinata and creates necessary indices:
    1. FASTA index (samtools faidx)
    2. BWA index (bwa index)

    Args:
        ref_name: Reference genome name (e.g., "GRCh38.fa")

    Returns:
        Reference object with all indices
    """
    refs = await hydrate({"type": "reference", "build": ref_name})
    ref = next((r for r in refs if isinstance(r, Reference)), None)
    if not ref:
        raise ValueError(f"Reference not found for build: {ref_name}")
    ref = await samtools_faidx(ref)
    ref = await bwa_index(ref)
    return ref


@gatk_env.task
async def align_sample(
    sample_id: str,
    ref: Reference,
    known_sites: list[str] | None = None,
    apply_bqsr: bool = False,
) -> Alignment:
    """
    Align a single sample's reads to reference and optionally apply BQSR.

    Hydrates reads from Pinata and runs fq2bam for alignment,
    sorting, and duplicate marking. Optionally applies Base Quality
    Score Recalibration (BQSR) if known_sites are provided.

    Args:
        sample_id: Sample identifier for querying reads
        ref: Prepared reference genome
        known_sites: List of known variant VCF filenames for BQSR
                    (e.g., ["dbsnp_146.hg38.vcf.gz"])
        apply_bqsr: Whether to apply BQSR (default: False)
                   If True, known_sites must be provided

    Returns:
        Alignment object with sorted, duplicate-marked BAM
        (optionally BQSR-recalibrated)

    Raises:
        ValueError: If apply_bqsr=True but known_sites is empty
    """
    if apply_bqsr and not known_sites:
        raise ValueError("known_sites must be provided when apply_bqsr=True")

    reads_list = await hydrate({"type": "reads", "sample_id": sample_id})
    reads = next((r for r in reads_list if isinstance(r, Reads)), None)
    if not reads:
        raise ValueError(f"Reads not found for sample_id: {sample_id}")
    alignment = await fq2bam(reads=reads, ref=ref)

    # Apply BQSR if requested
    if apply_bqsr and known_sites:
        recal_report = await baserecalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=known_sites,
        )
        alignment = await applybqsr(
            alignment=alignment,
            ref=ref,
            recal_report=recal_report,
        )

    return alignment


@gatk_env.task
async def call_variants_gvcf(
    alignment: Alignment,
    ref: Reference,
) -> Variants:
    """
    Call variants for a single sample in GVCF mode.

    Uses HaplotypeCaller to generate per-sample GVCF with genotype
    likelihoods for all sites (variant and reference).

    Args:
        alignment: Sorted, duplicate-marked BAM
        ref: Reference genome

    Returns:
        Variants object with indexed GVCF
    """
    gvcf = await haplotypecaller(
        alignment=alignment,
        ref=ref,
        output_gvcf=True,
    )
    # Index the GVCF for downstream processing (TODO: implement indexgvcf task)
    # gvcf = await indexgvcf(gvcf)
    return gvcf


@gatk_env.task
async def germline_single_sample(
    sample_id: str,
    ref_name: str,
    known_sites: list[str] | None = None,
    apply_bqsr: bool = False,
) -> tuple[Alignment, Variants]:
    """
    Single-sample germline short variant discovery workflow.

    Implements GATK Best Practices for a single sample:
    1. Prepare reference (index)
    2. Pre-process reads (align, mark duplicates, optional BQSR)
    3. Call variants (HaplotypeCaller in GVCF mode)
    4. Genotype (GenotypeGVCFs)

    Args:
        sample_id: Sample identifier
        ref_name: Reference genome name
        known_sites: List of known variant VCF filenames for BQSR
                    (e.g., ["dbsnp_146.hg38.vcf.gz"])
        apply_bqsr: Whether to apply BQSR (default: False)
                   Recommended for production use

    Returns:
        Tuple of (alignment, final_vcf)
        - alignment: Sorted, duplicate-marked BAM (optionally BQSR-recalibrated)
        - final_vcf: Final VCF with called variants

    Example:
        flyte.init_from_config()

        # Without BQSR (faster)
        run = flyte.run(
            germline_single_sample,
            sample_id="NA12878",
            ref_name="GRCh38.fa"
        )

        # With BQSR (recommended for production)
        run = flyte.run(
            germline_single_sample,
            sample_id="NA12878",
            ref_name="GRCh38.fa",
            known_sites=["dbsnp_146.hg38.vcf.gz"],
            apply_bqsr=True,
        )
        alignment, vcf = run.wait().outputs
    """
    # Step 1: Prepare reference
    ref = await prepare_reference(ref_name=ref_name)

    # Step 2: Pre-process reads (align, mark duplicates, optional BQSR)
    alignment = await align_sample(
        sample_id=sample_id,
        ref=ref,
        known_sites=known_sites,
        apply_bqsr=apply_bqsr,
    )

    # Step 3: Call variants (GVCF mode)
    gvcf = await call_variants_gvcf(alignment=alignment, ref=ref)

    # Step 4: Joint genotyping (single sample)
    vcf = await genotypegvcf(gvcf=gvcf, ref=ref)

    return alignment, vcf


@gatk_env.task
async def germline_cohort(
    sample_ids: list[str],
    ref_name: str,
    cohort_id: str = "cohort",
    known_sites: list[str] | None = None,
    apply_bqsr: bool = False,
) -> tuple[list[Alignment], list[Variants], Variants]:
    """
    Multi-sample (cohort) germline short variant discovery workflow.

    Implements GATK Best Practices joint calling workflow:
    1. Prepare reference (index)
    2. For each sample in parallel:
       a. Pre-process reads (align, mark duplicates, optional BQSR)
       b. Call variants (HaplotypeCaller in GVCF mode)
    3. Consolidate GVCFs (CombineGVCFs)
    4. Joint genotyping (GenotypeGVCFs)

    This approach enables incremental joint calling - new samples can be
    added to the cohort by generating their GVCFs and re-running the
    consolidation and genotyping steps.

    Args:
        sample_ids: List of sample identifiers
        ref_name: Reference genome name
        cohort_id: Identifier for the cohort (default: "cohort")
        known_sites: List of known variant VCF filenames for BQSR
        apply_bqsr: Whether to apply BQSR (default: False)

    Returns:
        Tuple of (alignments, gvcfs, joint_vcf)
        - alignments: List of sorted, duplicate-marked BAMs (one per sample)
        - gvcfs: List of per-sample GVCFs
        - joint_vcf: Final joint-called VCF with all samples

    Example:
        flyte.init_from_config()

        # Without BQSR
        run = flyte.run(
            germline_cohort,
            sample_ids=["NA12878", "NA12891", "NA12892"],
            ref_name="GRCh38.fa",
            cohort_id="family_trio"
        )

        # With BQSR (recommended)
        run = flyte.run(
            germline_cohort,
            sample_ids=["NA12878", "NA12891", "NA12892"],
            ref_name="GRCh38.fa",
            cohort_id="family_trio",
            known_sites=["dbsnp_146.hg38.vcf.gz"],
            apply_bqsr=True,
        )
        alignments, gvcfs, joint_vcf = run.wait().outputs

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360035890431-The-logic-of-joint-calling-for-germline-short-variants
    """
    if not sample_ids:
        raise ValueError("sample_ids list cannot be empty")

    # Step 1: Prepare reference
    ref = await prepare_reference(ref_name=ref_name)

    # Step 2: Process each sample in parallel (preprocess + call variants)
    async def process_sample(sample_id: str) -> tuple[Alignment, Variants]:
        alignment = await align_sample(
            sample_id=sample_id,
            ref=ref,
            known_sites=known_sites,
            apply_bqsr=apply_bqsr,
        )
        gvcf = await call_variants_gvcf(alignment=alignment, ref=ref)
        return alignment, gvcf

    # Run all samples in parallel
    results = await asyncio.gather(*[process_sample(sid) for sid in sample_ids])

    # Unpack results
    alignments = [r[0] for r in results]
    gvcfs = [r[1] for r in results]

    # Step 3: Consolidate GVCFs
    combined_gvcf = await combinegvcfs(gvcfs=gvcfs, ref=ref, cohort_id=cohort_id)

    # Step 4: Joint genotyping
    joint_vcf = await genotypegvcf(gvcf=combined_gvcf, ref=ref)

    return alignments, gvcfs, joint_vcf


@gatk_env.task
async def germline_from_gvcfs(
    gvcfs: list[Variants],
    ref_name: str,
    cohort_id: str = "cohort",
) -> Variants:
    """
    Joint genotyping from existing GVCFs.

    This workflow is useful for incremental joint calling - when you have
    existing per-sample GVCFs and want to add new samples or re-run
    joint genotyping.

    Args:
        gvcfs: List of per-sample GVCF Variants objects
        ref_name: Reference genome name
        cohort_id: Identifier for the cohort (default: "cohort")

    Returns:
        Final joint-called VCF with all samples

    Example:
        # Add a new sample to existing cohort
        new_gvcf = await call_variants_gvcf(new_alignment, ref)
        all_gvcfs = existing_gvcfs + [new_gvcf]
        joint_vcf = await germline_from_gvcfs(
            gvcfs=all_gvcfs,
            ref_name="GRCh38.fa",
            cohort_id="updated_cohort"
        )
    """
    if not gvcfs:
        raise ValueError("gvcfs list cannot be empty")

    # Prepare reference
    ref = await prepare_reference(ref_name=ref_name)

    # Consolidate GVCFs
    combined_gvcf = await combinegvcfs(gvcfs=gvcfs, ref=ref, cohort_id=cohort_id)

    # Joint genotyping
    joint_vcf = await genotypegvcf(gvcf=combined_gvcf, ref=ref)

    return joint_vcf


@gatk_env.task
async def germline_cohort_with_vqsr(
    sample_ids: list[str],
    ref_name: str,
    cohort_id: str = "cohort",
    known_sites: list[str] | None = None,
    apply_bqsr: bool = False,
    vqsr_snp_resources: list[VQSRResource] | None = None,
    vqsr_indel_resources: list[VQSRResource] | None = None,
    snp_truth_sensitivity: float = 99.0,
    indel_truth_sensitivity: float = 99.0,
) -> tuple[list[Alignment], list[Variants], Variants, Variants]:
    """
    Complete germline short variant discovery workflow with VQSR filtering.

    Implements the full GATK Best Practices pipeline including VQSR filtering
    for production-quality variant calls:
    1. Prepare reference (index)
    2. For each sample in parallel:
       a. Pre-process reads (align, mark duplicates, optional BQSR)
       b. Call variants (HaplotypeCaller in GVCF mode)
    3. Consolidate GVCFs (CombineGVCFs)
    4. Joint genotyping (GenotypeGVCFs)
    5. Variant filtration (VQSR for SNPs and INDELs)

    Args:
        sample_ids: List of sample identifiers
        ref_name: Reference genome name
        cohort_id: Identifier for the cohort (default: "cohort")
        known_sites: List of known variant VCF filenames for BQSR
        apply_bqsr: Whether to apply BQSR (default: False)
        vqsr_snp_resources: VQSR resources for SNP recalibration (required for VQSR)
        vqsr_indel_resources: VQSR resources for INDEL recalibration (required for VQSR)
        snp_truth_sensitivity: SNP filtering sensitivity threshold (default: 99.0)
        indel_truth_sensitivity: INDEL filtering sensitivity threshold (default: 99.0)

    Returns:
        Tuple of (alignments, gvcfs, joint_vcf, filtered_vcf)
        - alignments: List of sorted, duplicate-marked BAMs (one per sample)
        - gvcfs: List of per-sample GVCFs
        - joint_vcf: Unfiltered joint-called VCF with all samples
        - filtered_vcf: Final VQSR-filtered VCF (production-quality)

    Example:
        from stargazer.tasks import VQSRResource

        # Define VQSR resources for SNPs
        snp_resources = [
            VQSRResource(
                name="hapmap", vcf_name="hapmap_3.3.hg38.vcf.gz",
                known="false", training="true", truth="true", prior="15.0"
            ),
            VQSRResource(
                name="omni", vcf_name="1000G_omni2.5.hg38.vcf.gz",
                known="false", training="true", truth="true", prior="12.0"
            ),
            VQSRResource(
                name="1000G", vcf_name="1000G_phase1.snps.high_confidence.hg38.vcf.gz",
                known="false", training="true", truth="false", prior="10.0"
            ),
            VQSRResource(
                name="dbsnp", vcf_name="dbsnp_146.hg38.vcf.gz",
                known="true", training="false", truth="false", prior="2.0"
            ),
        ]

        # Define VQSR resources for INDELs
        indel_resources = [
            VQSRResource(
                name="mills", vcf_name="Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
                known="false", training="true", truth="true", prior="12.0"
            ),
            VQSRResource(
                name="dbsnp", vcf_name="dbsnp_146.hg38.vcf.gz",
                known="true", training="false", truth="false", prior="2.0"
            ),
        ]

        flyte.init_from_config()

        run = flyte.run(
            germline_cohort_with_vqsr,
            sample_ids=["NA12878", "NA12891", "NA12892"],
            ref_name="GRCh38.fa",
            cohort_id="family_trio",
            known_sites=["dbsnp_146.hg38.vcf.gz"],
            apply_bqsr=True,
            vqsr_snp_resources=snp_resources,
            vqsr_indel_resources=indel_resources,
        )
        alignments, gvcfs, joint_vcf, filtered_vcf = run.wait().outputs

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
    """
    # Run basic cohort workflow
    alignments, gvcfs, joint_vcf = await germline_cohort(
        sample_ids=sample_ids,
        ref_name=ref_name,
        cohort_id=cohort_id,
        known_sites=known_sites,
        apply_bqsr=apply_bqsr,
    )

    # Prepare reference for VQSR
    ref = await prepare_reference(ref_name=ref_name)

    # Apply VQSR filtering if resources provided
    if vqsr_snp_resources and vqsr_indel_resources:
        # SNP recalibration

        snp_recal, snp_tranches = await variantrecalibrator(
            vcf=joint_vcf,
            ref=ref,
            resources=vqsr_snp_resources,
            annotations=["QD", "MQRankSum", "ReadPosRankSum", "FS", "MQ", "SOR"],
            mode="SNP",
        )

        # Apply SNP filtering
        snp_filtered_vcf = await applyvqsr(
            vcf=joint_vcf,
            recal_file=snp_recal,
            tranches_file=snp_tranches,
            ref=ref,
            mode="SNP",
            truth_sensitivity_filter_level=snp_truth_sensitivity,
        )

        # INDEL recalibration
        indel_recal, indel_tranches = await variantrecalibrator(
            vcf=snp_filtered_vcf,
            ref=ref,
            resources=vqsr_indel_resources,
            annotations=["QD", "MQRankSum", "ReadPosRankSum", "FS", "SOR"],
            mode="INDEL",
        )

        # Apply INDEL filtering
        final_filtered_vcf = await applyvqsr(
            vcf=snp_filtered_vcf,
            recal_file=indel_recal,
            tranches_file=indel_tranches,
            ref=ref,
            mode="INDEL",
            truth_sensitivity_filter_level=indel_truth_sensitivity,
        )

        return alignments, gvcfs, joint_vcf, final_filtered_vcf
    else:
        # Return joint VCF without VQSR filtering (not recommended for production)
        return alignments, gvcfs, joint_vcf, joint_vcf


if __name__ == "__main__":
    import pprint

    flyte.init_from_config()

    # Example: Single sample
    print("Running single-sample germline workflow...")
    run = flyte.with_runcontext(mode="local").run(
        germline_single_sample,
        sample_id="NA12829",
        ref_name="GRCh38_TP53.fa",
    )
    run.wait()
    pprint.pprint(run.outputs)
