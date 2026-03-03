"""
haplotype_caller task for Stargazer.

Calls germline SNPs and indels via local re-assembly of haplotypes using
GATK HaplotypeCaller in GVCF mode.
"""

import stargazer.utils.storage as _storage
from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment, Variants
from stargazer.types.variants import VariantsFile
from stargazer.utils import _run


@gatk_env.task
async def haplotype_caller(
    alignment: Alignment,
    ref: Reference,
) -> Variants:
    """
    Call germline variants in GVCF mode using GATK HaplotypeCaller.

    Runs HaplotypeCaller with --emit-ref-confidence GVCF, producing a
    per-sample GVCF with genotype likelihoods at every site. The GVCF
    can be passed directly to genotype_gvcf (single-sample) or
    combine_gvcfs followed by genotype_gvcf (cohort joint-calling).

    Args:
        alignment: Sorted, duplicate-marked BAM (BQSR-recalibrated recommended)
        ref: Reference genome with FASTA index and sequence dictionary

    Returns:
        Variants object containing the per-sample GVCF

    Raises:
        ValueError: If required input files are missing or not fetched
        FileNotFoundError: If HaplotypeCaller fails to produce output

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller
    """
    await alignment.fetch()
    await ref.fetch()

    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path

    if not alignment.alignment or not alignment.alignment.path:
        raise ValueError("Alignment BAM file not available or not fetched")
    bam_path = alignment.alignment.path

    output_dir = _storage.default_client.local_dir
    output_gvcf = output_dir / f"{alignment.sample_id}.g.vcf"

    cmd = [
        "gatk",
        "HaplotypeCaller",
        "-R",
        str(ref_path),
        "-I",
        str(bam_path),
        "-O",
        str(output_gvcf),
        "--emit-ref-confidence",
        "GVCF",
    ]

    await _run(cmd, cwd=str(output_dir))

    if not output_gvcf.exists():
        raise FileNotFoundError(
            f"HaplotypeCaller did not create output GVCF at {output_gvcf}"
        )

    build = ref.fasta.build if ref.fasta else None
    vcf_comp = VariantsFile()
    await vcf_comp.update(
        output_gvcf,
        sample_id=alignment.sample_id,
        caller="haplotype_caller",
        variant_type="gvcf",
        build=build,
        sample_count=1,
        source_samples=[alignment.sample_id],
    )

    return Variants(sample_id=alignment.sample_id, vcf=vcf_comp)
