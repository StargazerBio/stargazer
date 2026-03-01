"""
GATK Best Practices: Data Pre-processing for Variant Discovery

This workflow implements the complete GATK Best Practices pipeline for data
pre-processing before variant calling using GATK tools.

The pipeline consists of three main steps:
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

from stargazer.config import gatk_env
from stargazer.types import Reference, Reads, Alignment, KnownSites
from stargazer.tasks import (
    samtools_faidx,
    create_sequence_dictionary,
    bwa_index,
    bwa_mem,
    sort_sam,
    mark_duplicates,
    base_recalibrator,
    apply_bqsr,
)
from stargazer.utils.storage import default_client


@gatk_env.task
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
    fasta_files = await default_client.query(
        {"type": "reference", "component": "fasta", "build": ref_name}
    )
    if not fasta_files:
        raise ValueError(f"Reference not found for build: {ref_name}")
    ref = Reference(build=ref_name, fasta=fasta_files[0])
    ref = await samtools_faidx(ref)
    ref = await create_sequence_dictionary(ref)
    ref = await bwa_index(ref)
    return ref


@gatk_env.task
async def preprocess_sample(
    sample_id: str,
    ref: Reference,
    known_sites: list[KnownSites] | None = None,
    run_bqsr: bool = True,
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
        known_sites: List of Variants objects for known variant sites (dbSNP, known indels, etc.)
                    Required if run_bqsr=True
        run_bqsr: Whether to apply BQSR (default: True)
                  If True, known_sites must be provided

    Returns:
        Alignment object with sorted, duplicate-marked BAM
        (and optionally BQSR-recalibrated if run_bqsr=True)

    Raises:
        ValueError: If run_bqsr=True but known_sites is empty/None

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")

        # With BQSR (recommended)
        alignment = await preprocess_sample(
            sample_id="NA12878",
            ref=ref,
            known_sites=[mills_variants, dbsnp_variants],
            run_bqsr=True,
        )

        # Without BQSR (faster, but less accurate)
        alignment = await preprocess_sample(
            sample_id="NA12878",
            ref=ref,
            run_bqsr=False,
        )
    """
    if run_bqsr and not known_sites:
        raise ValueError(
            "known_sites must be provided when run_bqsr=True. "
            "Provide VCF files like dbSNP, Mills indels, or set run_bqsr=False."
        )

    # Query reads from storage
    r1_files = await default_client.query(
        {"type": "reads", "component": "r1", "sample_id": sample_id}
    )
    if not r1_files:
        raise ValueError(f"Reads not found for sample_id: {sample_id}")
    r2_files = await default_client.query(
        {"type": "reads", "component": "r2", "sample_id": sample_id}
    )
    reads = Reads(
        sample_id=sample_id,
        r1=r1_files[0],
        r2=r2_files[0] if r2_files else None,
    )

    # Step 1: Align reads to reference using BWA-MEM
    alignment = await bwa_mem(reads=reads, ref=ref)

    # Step 2: Sort by coordinate
    alignment = await sort_sam(alignment=alignment, ref=ref, sort_order="coordinate")

    # Step 3: Mark duplicates
    alignment = await mark_duplicates(alignment=alignment, ref=ref)

    # Step 4: BQSR (optional but recommended)
    if run_bqsr and known_sites:
        # Generate recalibration table (sets alignment.bqsr_report)
        alignment = await base_recalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=known_sites,
        )

        # Apply recalibration (reads alignment.bqsr_report)
        alignment = await apply_bqsr(alignment=alignment, ref=ref)

    return alignment
