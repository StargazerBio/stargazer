"""
GATK Best Practices: Germline Short Variant Discovery (SNPs + Indels)

Implements the GATK pipeline starting from preprocessed BAM files:
    1. HaplotypeCaller  — per-sample GVCF
    2. CombineGVCFs     — merge per-sample GVCFs
    3. GenotypeGVCFs    — joint genotyping

Prerequisites:
    Reference and sample alignments must already be in storage (run prepare_reference
    and preprocess_sample first).

Reference:
    https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
"""

import asyncio

import stargazer.utils.storage as _storage
from stargazer.config import gatk_env
from stargazer.types import Variants
from stargazer.types.constellation import assemble
from stargazer.tasks import (
    haplotype_caller,
    combine_gvcfs,
    genotype_gvcf,
)


@gatk_env.task
async def germline_short_variant_discovery(
    build: str,
    sample_ids: list[str],
    cohort_id: str = "cohort",
) -> Variants:
    """
    Germline short variant discovery from preprocessed BAMs.

    Assembles the reference and per-sample alignments from storage, runs
    HaplotypeCaller in parallel across all samples, then combines and
    joint-genotypes to produce a final VCF.

    Args:
        build: Reference genome build identifier
        sample_ids: List of sample identifiers to process
        cohort_id: Identifier for the combined GVCF (default: "cohort")

    Returns:
        Joint-genotyped Variants asset
    """
    # Assemble reference
    c_ref = await assemble(build=build, asset="reference")
    ref = c_ref.reference
    if ref is None:
        raise ValueError(f"No reference found for build={build!r}")
    await _storage.default_client.download(ref)

    async def call_sample(sample_id: str) -> Variants:
        c = await assemble(sample_id=sample_id, asset="alignment")
        alignment = c.alignment
        if alignment is None:
            raise ValueError(f"No alignment found for sample_id={sample_id!r}")
        if isinstance(alignment, list):
            # Use the most recent (last) alignment if multiple exist
            alignment = alignment[-1]
        await _storage.default_client.download(alignment)
        return await haplotype_caller(alignment=alignment, ref=ref)

    # 1. HaplotypeCaller — per-sample GVCFs in parallel
    gvcfs = list(await asyncio.gather(*[call_sample(sid) for sid in sample_ids]))

    # 2. CombineGVCFs — merge into a single GVCF
    combined = await combine_gvcfs(gvcfs=gvcfs, ref=ref, cohort_id=cohort_id)

    # 3. GenotypeGVCFs — joint genotyping
    return await genotype_gvcf(gvcf=combined, ref=ref)
