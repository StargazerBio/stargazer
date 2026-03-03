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
from stargazer.types import Reference, Reads, Alignment, Variants
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


@gatk_env.task
async def prepare_reference(data: list[Reference]) -> Reference:
    """
    Prepare reference genome for alignment and variant calling.

    Creates necessary indices from a hydrated Reference:
    1. FASTA index (samtools faidx) - Required for alignment and BQSR
    2. Sequence dictionary (GATK CreateSequenceDictionary)
    3. BWA index (bwa index) - Required for BWA-MEM alignment

    Args:
        data: List containing a single Reference with fasta component

    Returns:
        Reference object with all indices
    """
    ref = data[0]
    ref = await samtools_faidx(ref)
    ref = await create_sequence_dictionary(ref)
    ref = await bwa_index(ref)
    return ref


@gatk_env.task
async def preprocess_sample(
    data: list[Reference | Reads | Variants],
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
        data: Hydrated BioTypes containing Reference, Reads, and optionally
              Variants with known_sites for BQSR
        run_bqsr: Whether to apply BQSR (default: True)
                  If True, data must contain Variants with known_sites

    Returns:
        Alignment object with sorted, duplicate-marked BAM
        (and optionally BQSR-recalibrated if run_bqsr=True)

    Raises:
        ValueError: If run_bqsr=True but no known_sites found in data
    """
    ref = next(d for d in data if isinstance(d, Reference))
    reads = next(d for d in data if isinstance(d, Reads))
    known_sites = [
        d.known_sites for d in data if isinstance(d, Variants) and d.known_sites
    ]

    if run_bqsr and not known_sites:
        raise ValueError(
            "known_sites must be provided when run_bqsr=True. "
            "Provide Variants with known_sites component, or set run_bqsr=False."
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
