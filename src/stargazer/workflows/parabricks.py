"""
Genomics workflows using NVIDIA Parabricks tasks.

This module provides example workflows that combine Parabricks tasks
into complete genomics analysis pipelines.
"""

from typing import List

import flyte
from flyte.io import File

from stargazer.tasks.parabricks import (
    parabricks_env,
    fq2bam,
    deepvariant,
    haplotypecaller,
)


@parabricks_env.task
async def genomics_pipeline(
    ref: File,
    fastq_r1: File,
    fastq_r2: File,
    known_sites: List[File],
    use_deepvariant: bool = True,
) -> File:
    """
    Example genomics pipeline: FASTQ to VCF.

    Args:
        ref: Reference genome
        fastq_r1: Forward FASTQ reads
        fastq_r2: Reverse FASTQ reads
        known_sites: Known variants for BQSR
        use_deepvariant: Use DeepVariant (True) or HaplotypeCaller (False)

    Returns:
        Final VCF file with variant calls
    """
    # Step 1: Align FASTQ to BAM with fq2bam
    fq2bam_result = await fq2bam(
        ref=ref,
        in_fq_r1=fastq_r1,
        in_fq_r2=fastq_r2,
        known_sites=known_sites,
        out_recal_path="recal.txt",
    )

    # Step 2: Call variants
    if use_deepvariant:
        variant_result = await deepvariant(
            ref=ref,
            in_bam=fq2bam_result.bam,
            mode="shortread",
        )
    else:
        variant_result = await haplotypecaller(
            ref=ref,
            in_bam=fq2bam_result.bam,
            in_recal_file=fq2bam_result.recal_file,
        )

    return variant_result.variants
