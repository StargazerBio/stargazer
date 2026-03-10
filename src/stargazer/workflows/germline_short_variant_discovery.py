"""
# GATK Best Practices: Germline Short Variant Discovery (SNPs + Indels)

Implements the full GATK pipeline from preprocessed BAMs:
    1. HaplotypeCaller  — per-sample GVCF (parallel)
    2. joint_call_gvcfs — GenomicsDBImport + GenotypeGVCFs in one task
    3. VariantRecalibrator (INDEL) — build VQSR model
    4. ApplyVQSR INDEL — filter indels → final VCF

Prerequisites:
    Reference and sample alignments must already be in storage (run prepare_reference
    and preprocess_sample first). VQSR training resources (HapMap, omni, 1000G,
    mills, dbSNP) must be stored with build, resource_name, known, training,
    truth, and prior keyvalues, tagged with vqsr_mode=INDEL.

Reference:
    https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels

spec: [docs/architecture/workflows.md](../architecture/workflows.md)
"""

import asyncio

from stargazer.config import gatk_env
from stargazer.types import Variants
from stargazer.types.asset import assemble
from stargazer.tasks import (
    haplotype_caller,
    joint_call_gvcfs,
    variant_recalibrator,
    apply_vqsr,
)


@gatk_env.task(cache="disable")
async def germline_short_variant_discovery(
    build: str,
    cohort_id: str = "cohort",
) -> Variants:
    """
    Germline short variant discovery from preprocessed BAMs.

    Assembles all BQSR-applied alignments and reference from storage, then runs
    the full GATK Best Practices pipeline through VQSR filtering.

    Expects preprocess_sample to have been run first — alignments must have
    bqsr_applied=true.

    Args:
        build: Reference genome build identifier (e.g. "GRCh38")
        cohort_id: Identifier for the cohort output (default: "cohort")

    Returns:
        VQSR-filtered joint-genotyped Variants asset
    """
    # Assemble reference first so we can filter alignments by reference_cid
    refs = await assemble(build=build, asset="reference")
    if not refs:
        raise ValueError(f"No reference found for build={build!r}")
    ref = refs[0]

    alignments, indel_resources = await asyncio.gather(
        assemble(reference_cid=ref.cid, asset="alignment", bqsr_applied="true"),
        assemble(build=build, asset="known_sites", vqsr_mode="INDEL"),
    )

    if not alignments:
        raise ValueError(
            f"No BQSR-applied alignments found for build={build!r}. "
            "Run preprocess_sample first."
        )

    if not indel_resources:
        raise ValueError(f"No INDEL VQSR resources for build={build!r}")

    # 1. HaplotypeCaller — per-sample GVCFs in parallel
    gvcfs = list(
        await asyncio.gather(
            *[haplotype_caller(alignment=aln, ref=ref) for aln in alignments]
        )
    )

    # 2. GenomicsDBImport + GenotypeGVCFs — joint calling
    raw_vcf = await joint_call_gvcfs(
        gvcfs=gvcfs, ref=ref, intervals=ref.contigs, cohort_id=cohort_id
    )

    # 3. VariantRecalibrator — INDEL model
    indel_model = await variant_recalibrator(
        vcf=raw_vcf, ref=ref, resources=indel_resources, mode="INDEL"
    )

    # 4. ApplyVQSR — INDEL
    return await apply_vqsr(vcf=raw_vcf, ref=ref, vqsr_model=indel_model)
