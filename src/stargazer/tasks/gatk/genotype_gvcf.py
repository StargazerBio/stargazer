"""
GenotypeGVCF task for Stargazer.

Performs joint genotyping by converting GVCF to VCF using GATK GenotypeGVCFs.
This is a key step in the GATK Best Practices germline short variant discovery workflow.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
from stargazer.types.variants import VariantsFile
from stargazer.utils import _run


@gatk_env.task
async def genotype_gvcf(
    gvcf: Variants,
    ref: Reference,
) -> Variants:
    """
    Convert GVCF to VCF using GATK GenotypeGVCFs (joint genotyping).

    This tool applies GATK GenotypeGVCFs for joint genotyping,
    converting from g.vcf format to regular VCF format. This utilizes the
    HaplotypeCaller genotype likelihoods to produce final variant calls.

    For single-sample calling, this converts a sample's GVCF to final VCF.
    For multi-sample calling, first combine GVCFs using combine_gvcfs, then
    run genotype_gvcf on the combined GVCF.

    Args:
        gvcf: Variants object containing a GVCF file (from HaplotypeCaller or CombineGVCFs)
        ref: Reference genome used for variant calling

    Returns:
        Variants object with final VCF variant calls

    Raises:
        ValueError: If input is not a GVCF file
        FileNotFoundError: If genotyping fails to produce output

    Example:
        # Single sample genotyping
        gvcf = await haplotypecaller(alignment=alignment, ref=ref, output_gvcf=True)
        vcf = await genotype_gvcf(gvcf=gvcf, ref=ref)

        # Multi-sample genotyping
        combined = await combine_gvcfs(gvcfs=[gvcf1, gvcf2, gvcf3], ref=ref)
        joint_vcf = await genotype_gvcf(gvcf=combined, ref=ref)

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037057852-GenotypeGVCFs
        https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
    """
    # Validate that this is a GVCF
    if not gvcf.vcf or gvcf.vcf.variant_type != "gvcf":
        raise ValueError(
            f"genotype_gvcf requires a GVCF file, but got VCF. sample_id={gvcf.sample_id}"
        )

    # Fetch all input files to cache
    await gvcf.fetch()
    await ref.fetch()

    # Get paths to input files
    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path
    if not gvcf.vcf or not gvcf.vcf.path:
        raise ValueError("GVCF file not available or not fetched")
    gvcf_path = gvcf.vcf.path

    # Create output VCF path
    output_dir = ref_path.parent
    output_vcf = output_dir / f"{gvcf.sample_id}_genotyped.vcf"

    # Build GATK GenotypeGVCFs command
    cmd = [
        "gatk",
        "GenotypeGVCFs",
        "-R",
        str(ref_path),
        "-V",
        str(gvcf_path),
        "-O",
        str(output_vcf),
    ]

    # Execute GenotypeGVCFs
    stdout, stderr = await _run(cmd, cwd=str(output_dir))

    # Verify output VCF was created
    if not output_vcf.exists():
        raise FileNotFoundError(
            f"GenotypeGVCFs did not create output VCF at {output_vcf}. stderr: {stderr}"
        )

    # Upload output VCF and build Variants
    build = ref.fasta.build if ref.fasta else None
    source_samples = gvcf.vcf.source_samples or [gvcf.sample_id]
    vcf_comp = VariantsFile()
    await vcf_comp.update(
        output_vcf,
        sample_id=gvcf.sample_id,
        caller="genotype_gvcf",
        variant_type="vcf",
        build=build,
        sample_count=len(source_samples),
        source_samples=source_samples,
    )

    return Variants(sample_id=gvcf.sample_id, vcf=vcf_comp)
