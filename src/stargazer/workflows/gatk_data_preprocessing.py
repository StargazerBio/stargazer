"""
GATK Best Practices: Data Pre-processing for Variant Discovery

This workflow implements the complete GATK Best Practices pipeline for data
pre-processing before variant calling using GATK tools.

The pipeline consists of four main steps:
1. Read Mapping (BWA-MEM) - Align reads to reference genome
2. Sort and Mark Duplicates - Sort reads and identify PCR/optical duplicates
3. Base Quality Score Recalibration (BQSR) - Correct systematic biases in quality scores

All steps use standard GATK/BWA tools for maximum compatibility.
BQSR is optional but recommended and requires known variant sites (dbSNP, known indels).

References:
    - https://gatk.broadinstitute.org/hc/en-us/articles/360035535912-Data-pre-processing-for-variant-discovery
    - https://bio-bwa.sourceforge.net/bwa.shtml
    - https://gatk.broadinstitute.org/hc/en-us/articles/360037052812-MarkDuplicates-Picard
"""

import asyncio

import flyte

from stargazer.config import pb_env
from stargazer.types import Reference, Reads, Alignment
from stargazer.tasks import (
    samtools_faidx,
    bwa_index,
    bwa_mem,
    sortsam,
    markduplicates,
    baserecalibrator,
    applybqsr,
)


@pb_env.task
async def prepare_reference(ref_name: str) -> Reference:
    """
    Prepare reference genome for alignment and variant calling.

    Hydrates reference from Pinata and creates necessary indices:
    1. FASTA index (samtools faidx) - Required for alignment and BQSR
    2. BWA index (bwa index) - Required for BWA-MEM alignment

    Args:
        ref_name: Reference genome name (e.g., "GRCh38.fa")

    Returns:
        Reference object with all indices

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")
    """
    ref = await Reference.pinata_hydrate(ref_name=ref_name)
    ref = await samtools_faidx(ref)
    ref = await bwa_index(ref)
    return ref


@pb_env.task
async def preprocess_sample(
    sample_id: str,
    ref: Reference,
    known_sites: list[str] | None = None,
    apply_bqsr: bool = True,
) -> Alignment:
    """
    Pre-process a single sample's reads for variant calling.

    Implements GATK Best Practices data pre-processing:
    1. Align reads to reference using BWA-MEM
    2. Sort by coordinate using GATK SortSam
    3. Mark duplicates using GATK MarkDuplicates
    4. (Optional) Apply Base Quality Score Recalibration using GATK BaseRecalibrator + ApplyBQSR

    All steps use standard GATK/BWA tools.

    Args:
        sample_id: Sample identifier for querying reads from Pinata
        ref: Prepared reference genome (with indices)
        known_sites: List of known variant VCF filenames for BQSR
                    (e.g., ["dbsnp_146.hg38.vcf.gz", "Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"])
                    Required if apply_bqsr=True
        apply_bqsr: Whether to apply BQSR (default: True)
                   If True, known_sites must be provided

    Returns:
        Alignment object with sorted, duplicate-marked BAM
        (and optionally BQSR-recalibrated if apply_bqsr=True)

    Raises:
        ValueError: If apply_bqsr=True but known_sites is empty/None

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")

        # With BQSR (recommended)
        alignment = await preprocess_sample(
            sample_id="NA12878",
            ref=ref,
            known_sites=["dbsnp_146.hg38.vcf.gz", "Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"],
            apply_bqsr=True,
        )

        # Without BQSR (faster, but less accurate)
        alignment = await preprocess_sample(
            sample_id="NA12878",
            ref=ref,
            apply_bqsr=False,
        )
    """
    if apply_bqsr and not known_sites:
        raise ValueError(
            "known_sites must be provided when apply_bqsr=True. "
            "Provide VCF files like dbSNP, Mills indels, or set apply_bqsr=False."
        )

    # Hydrate reads from Pinata
    reads = await Reads.pinata_hydrate(sample_id=sample_id)

    # Step 1: Align reads to reference using BWA-MEM
    alignment = await bwa_mem(reads=reads, ref=ref)

    # Step 2: Sort by coordinate
    alignment = await sortsam(alignment=alignment, ref=ref, sort_order="coordinate")

    # Step 3: Mark duplicates
    alignment = await markduplicates(alignment=alignment, ref=ref)

    # Step 4: BQSR (optional but recommended)
    if apply_bqsr and known_sites:
        # Generate recalibration table
        recal_report = await baserecalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=known_sites,
        )

        # Apply recalibration
        alignment = await applybqsr(
            alignment=alignment,
            ref=ref,
            recal_report=recal_report,
        )

    return alignment


@pb_env.task
async def preprocess_cohort(
    sample_ids: list[str],
    ref_name: str,
    known_sites: list[str] | None = None,
    apply_bqsr: bool = True,
) -> list[Alignment]:
    """
    Pre-process multiple samples in parallel for variant calling.

    Implements GATK Best Practices data pre-processing for a cohort:
    1. Prepare reference (shared across all samples)
    2. For each sample in parallel:
       a. Align reads to reference using BWA-MEM
       b. Sort by coordinate using GATK SortSam
       c. Mark duplicates using GATK MarkDuplicates
       d. (Optional) Apply BQSR using GATK BaseRecalibrator + ApplyBQSR

    Args:
        sample_ids: List of sample identifiers
        ref_name: Reference genome name
        known_sites: List of known variant VCF filenames for BQSR
        apply_bqsr: Whether to apply BQSR (default: True)

    Returns:
        List of Alignment objects (one per sample), ready for variant calling

    Raises:
        ValueError: If sample_ids is empty or if apply_bqsr=True but known_sites is empty

    Example:
        alignments = await preprocess_cohort(
            sample_ids=["NA12878", "NA12891", "NA12892"],
            ref_name="GRCh38.fa",
            known_sites=["dbsnp_146.hg38.vcf.gz"],
            apply_bqsr=True,
        )
    """
    if not sample_ids:
        raise ValueError("sample_ids list cannot be empty")

    if apply_bqsr and not known_sites:
        raise ValueError(
            "known_sites must be provided when apply_bqsr=True. "
            "Provide VCF files like dbSNP, Mills indels, or set apply_bqsr=False."
        )

    # Prepare reference (shared across all samples)
    ref = await prepare_reference(ref_name=ref_name)

    # Process all samples in parallel
    alignments = await asyncio.gather(
        *[
            preprocess_sample(
                sample_id=sample_id,
                ref=ref,
                known_sites=known_sites,
                apply_bqsr=apply_bqsr,
            )
            for sample_id in sample_ids
        ]
    )

    return list(alignments)


@pb_env.task
async def apply_bqsr_to_alignment(
    alignment: Alignment,
    ref: Reference,
    known_sites: list[str],
) -> Alignment:
    """
    Apply BQSR to an existing alignment.

    Use this when you have an alignment that was created without BQSR
    and want to apply recalibration afterwards.

    Args:
        alignment: Existing alignment (sorted, duplicates marked)
        ref: Reference genome
        known_sites: List of known variant VCF filenames

    Returns:
        New Alignment object with BQSR applied

    Example:
        # Recalibrate an existing BAM
        recalibrated = await apply_bqsr_to_alignment(
            alignment=existing_alignment,
            ref=ref,
            known_sites=["dbsnp_146.hg38.vcf.gz"],
        )
    """
    if not known_sites:
        raise ValueError("known_sites list cannot be empty for BQSR")

    # Generate recalibration table
    recal_report = await baserecalibrator(
        alignment=alignment,
        ref=ref,
        known_sites=known_sites,
    )

    # Apply recalibration
    recalibrated_alignment = await applybqsr(
        alignment=alignment,
        ref=ref,
        recal_report=recal_report,
    )

    return recalibrated_alignment


if __name__ == "__main__":
    import pprint

    flyte.init_from_config()

    # Example: Single sample preprocessing with BQSR
    print("Running single-sample data preprocessing...")
    run = flyte.with_runcontext(mode="local").run(
        preprocess_sample,
        sample_id="NA12829",
        ref_name="GRCh38_TP53.fa",
        known_sites=["dbsnp_146.hg38.vcf.gz"],
        apply_bqsr=True,
    )
    run.wait()
    pprint.pprint(run.outputs)
