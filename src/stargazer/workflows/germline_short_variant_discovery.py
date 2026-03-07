"""
GATK Best Practices: Germline Short Variant Discovery (SNPs + Indels)

Implements the full GATK pipeline from preprocessed BAMs:
    1. HaplotypeCaller  — per-sample GVCF (parallel)
    2. joint_call_gvcfs — GenomicsDBImport + GenotypeGVCFs in one task
    4. VariantRecalibrator (SNP + INDEL in parallel) — build VQSR models
    5. ApplyVQSR SNP    — filter SNPs at 99.5% sensitivity
    6. ApplyVQSR INDEL  — filter INDELs at 99.0% sensitivity → final VCF

Prerequisites:
    Reference and sample alignments must already be in storage (run prepare_reference
    and preprocess_sample first). VQSR training resources (HapMap, omni, 1000G,
    mills, dbSNP) must be stored with build, resource_name, known, training,
    truth, and prior keyvalues, tagged with vqsr_mode=SNP or vqsr_mode=INDEL.

Reference:
    https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
"""

import asyncio

from stargazer.config import gatk_env
from stargazer.types import Alignment, KnownSites, Reference, Variants
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
    sample_ids: list[str],
    cohort_id: str = "cohort",
) -> Variants:
    """
    Germline short variant discovery from preprocessed BAMs.

    Assembles the reference and per-sample alignments from storage, then runs
    the full GATK Best Practices pipeline through VQSR filtering.

    Expects preprocess_sample to have been run first — alignments must have
    bqsr_applied=true.

    Args:
        build: Reference genome build identifier (e.g. "GRCh38")
        sample_ids: List of sample identifiers to process
        cohort_id: Identifier for the cohort output (default: "cohort")

    Returns:
        VQSR-filtered joint-genotyped Variants asset
    """
    # Assemble reference + fetch companions (.fai, .dict)
    ref_assets = await assemble(build=build, asset="reference")
    refs = [a for a in ref_assets if isinstance(a, Reference)]
    if not refs:
        raise ValueError(f"No reference found for build={build!r}")
    ref = refs[0]
    await ref.fetch()

    # 1. HaplotypeCaller — per-sample GVCFs in parallel
    async def call_sample(sample_id: str) -> Variants:
        aln_assets = await assemble(
            sample_id=sample_id, asset="alignment", bqsr_applied="true"
        )
        alignments = [a for a in aln_assets if isinstance(a, Alignment)]
        if not alignments:
            raise ValueError(
                f"No BQSR-applied alignment for sample_id={sample_id!r}. "
                f"Run preprocess_sample first."
            )
        return await haplotype_caller(alignment=alignments[-1], ref=ref)

    gvcfs = list(await asyncio.gather(*[call_sample(sid) for sid in sample_ids]))

    # 2. GenomicsDBImport + GenotypeGVCFs — joint calling
    raw_vcf = await joint_call_gvcfs(
        gvcfs=gvcfs, ref=ref, intervals=ref.contigs, cohort_id=cohort_id
    )

    # 3. VariantRecalibrator — build SNP and INDEL models in parallel
    async def get_vqsr_resources(mode: str) -> list[KnownSites]:
        assets = await assemble(build=build, asset="known_sites", vqsr_mode=mode)
        resources = [a for a in assets if isinstance(a, KnownSites)]
        if not resources:
            raise ValueError(
                f"No VQSR resources for build={build!r}, vqsr_mode={mode!r}"
            )
        return resources

    snp_resources, indel_resources = await asyncio.gather(
        get_vqsr_resources("SNP"), get_vqsr_resources("INDEL")
    )

    snp_model, indel_model = await asyncio.gather(
        variant_recalibrator(vcf=raw_vcf, ref=ref, resources=snp_resources, mode="SNP"),
        variant_recalibrator(
            vcf=raw_vcf, ref=ref, resources=indel_resources, mode="INDEL"
        ),
    )

    # 4. ApplyVQSR SNP then INDEL — sequential (INDEL filters SNP-filtered VCF)
    snp_filtered = await apply_vqsr(vcf=raw_vcf, ref=ref, vqsr_model=snp_model)
    return await apply_vqsr(vcf=snp_filtered, ref=ref, vqsr_model=indel_model)
