"""
### GATK Best Practices: Germline Short Variant Discovery (SNPs + Indels)

End-to-end GATK pipeline from raw reads to joint-genotyped variants:
    1. prepare_reference  — FASTA index, sequence dictionary, BWA-MEM2 index
    2. preprocess_sample  — align, sort, mark duplicates (per sample, parallel)
    3. haplotype_caller   — per-sample GVCF (parallel)
    4. joint_call_gvcfs   — GenomicsDBImport + GenotypeGVCFs

Reference:
    https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels

spec: [docs/architecture/workflows.md](../architecture/workflows.md)
"""

import asyncio

from stargazer.assets import Variants
from stargazer.config import gatk_env, log_execution
from stargazer.tasks import (
    haplotype_caller,
    joint_call_gvcfs,
)
from stargazer.workflows.gatk_data_preprocessing import (
    prepare_reference,
    preprocess_sample,
)


@gatk_env.task(cache="disable")
async def germline_short_variant_discovery(
    build: str,
    sample_ids: list[str],
    cohort_id: str = "cohort",
) -> Variants:
    """
    End-to-end germline short variant discovery from raw reads.

    Runs the full GATK best-practices pipeline:
    1. Reference preparation (indexing)
    2. Per-sample preprocessing (align, sort, mark duplicates) in parallel
    3. HaplotypeCaller per sample in parallel
    4. Joint genotyping (GenomicsDBImport + GenotypeGVCFs)

    Args:
        build: Reference genome build identifier (e.g. "GRCh38")
        sample_ids: List of sample identifiers to process
        cohort_id: Identifier for the cohort output (default: "cohort")

    Returns:
        Joint-genotyped Variants asset
    """
    log_execution()

    ref = await prepare_reference(build=build)

    alignments = list(
        await asyncio.gather(
            *[preprocess_sample(build=build, sample_id=sid) for sid in sample_ids]
        )
    )

    gvcfs = list(
        await asyncio.gather(
            *[haplotype_caller(alignment=aln, ref=ref) for aln in alignments]
        )
    )

    # Joint calling covers every contig: the task reads them from the
    # reference's .fai, which prepare_reference built.
    return await joint_call_gvcfs(gvcfs=gvcfs, ref=ref, cohort_id=cohort_id)
