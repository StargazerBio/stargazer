"""
Whole genome germline small variants workflow.

This workflow implements the complete NVIDIA Clara Parabricks germline variant calling pipeline:
1. Reference preparation (samtools faidx + bwa index)
2. FASTQ alignment (fq2bam)
3. Variant calling (DeepVariant and/or HaplotypeCaller)
"""

import flyte

from stargazer.config import pb_env
from stargazer.types import Reference, Reads, Alignment, Variants
from stargazer.tasks import (
    samtools_faidx,
    bwa_index,
    fq2bam,
    deepvariant,
    haplotypecaller,
)


@pb_env.task
async def wgs_germline_snv(
    sample_id: str,
    ref_name: str,
    run_deepvariant: bool = True,
    run_haplotypecaller: bool = True,
    output_gvcf: bool = False,
) -> tuple[Alignment, Variants | None, Variants | None]:
    """
    Complete whole genome germline small variant calling workflow.

    Implements the NVIDIA Clara Parabricks germline variant calling pipeline:
    1. Hydrate reference genome from Pinata
    2. Index reference (samtools faidx + bwa index)
    3. Hydrate reads (FASTQ) from Pinata
    4. Run fq2bam (alignment + sorting + markdups)
    5. Run DeepVariant (if enabled)
    6. Run HaplotypeCaller (if enabled)

    Args:
        sample_id: Sample identifier for querying reads
        ref_name: Reference genome name (e.g., "GRCh38_TP53.fa")
        run_deepvariant: Whether to run DeepVariant caller (default: True)
        run_haplotypecaller: Whether to run HaplotypeCaller (default: True)
        output_gvcf: Whether to output GVCF format (default: False)

    Returns:
        Tuple of (alignment, deepvariant_vcf, haplotypecaller_vcf)
        - alignment: Sorted, duplicate-marked BAM
        - deepvariant_vcf: DeepVariant VCF (None if disabled)
        - haplotypecaller_vcf: HaplotypeCaller VCF (None if disabled)

    Example:
        flyte.init_from_config()
        run = flyte.run(
            wgs_germline_snv,
            sample_id="NA12829",
            ref_name="GRCh38_TP53.fa"
        )
        print(run.url)
        run.wait()
        alignment, dv_vcf, hc_vcf = run.outputs
    """
    # Step 1-2: Reference preparation
    ref = await Reference.pinata_hydrate(ref_name=ref_name)
    ref = await samtools_faidx(ref)
    ref = await bwa_index(ref)

    # Step 3: Fetch reads
    reads = await Reads.pinata_hydrate(sample_id=sample_id)

    # Step 4: Alignment
    alignment = await fq2bam(reads=reads, ref=ref)

    # Step 5-6: Variant calling (can run in parallel if needed)
    deepvariant_vcf = None
    haplotypecaller_vcf = None

    if run_deepvariant:
        deepvariant_vcf = await deepvariant(
            alignment=alignment, ref=ref, output_gvcf=output_gvcf
        )

    if run_haplotypecaller:
        haplotypecaller_vcf = await haplotypecaller(
            alignment=alignment, ref=ref, output_gvcf=output_gvcf
        )

    return alignment, deepvariant_vcf, haplotypecaller_vcf


if __name__ == "__main__":
    import pprint

    flyte.init_from_config()
    r = flyte.with_runcontext(mode="local").run(
        wgs_germline_snv, sample_id="NA12829", ref_name="GRCh38_TP53.fa"
    )
    r.wait()
    pprint.pprint(r.outputs)
