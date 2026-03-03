"""
GATK Best Practices: Germline Short Variant Discovery (SNPs + Indels)

Implements the GATK pipeline starting from preprocessed BAM files:
    1. HaplotypeCaller  — per-sample GVCF
    2. CombineGVCFs     — merge per-sample GVCFs
    3. GenotypeGVCFs    — joint genotyping

Prerequisites:
    Inputs must be preprocessed with gatk_data_preprocessing.prepare_reference
    and gatk_data_preprocessing.preprocess_sample.

Reference:
    https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
"""

import asyncio

from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment, Variants
from stargazer.tasks import (
    haplotype_caller,
    combine_gvcfs,
    genotype_gvcf,
)


@gatk_env.task
async def germline_short_variant_discovery(
    data: list[Reference | Alignment],
    cohort_id: str = "cohort",
) -> Variants:
    """
    Germline short variant discovery from preprocessed BAMs.

    Runs the GATK Best Practices pipeline across all samples and returns
    a joint-genotyped VCF ready for downstream analysis.

    Args:
        data: Hydrated BioTypes containing one Reference and one or more Alignments
        cohort_id: Identifier for the combined GVCF (default: "cohort")

    Returns:
        Joint-genotyped Variants
    """
    ref = next(d for d in data if isinstance(d, Reference))
    alignments = [d for d in data if isinstance(d, Alignment)]

    # 1. HaplotypeCaller — per-sample GVCFs in parallel
    gvcfs = list(
        await asyncio.gather(
            *[haplotype_caller(alignment=a, ref=ref) for a in alignments]
        )
    )

    # 2. CombineGVCFs — merge into a single GVCF
    combined = await combine_gvcfs(gvcfs=gvcfs, ref=ref, cohort_id=cohort_id)

    # 3. GenotypeGVCFs — joint genotyping
    return await genotype_gvcf(gvcf=combined, ref=ref)
