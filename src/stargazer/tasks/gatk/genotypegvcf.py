"""
GenotypeGVCF task for Stargazer.

Performs joint genotyping by converting GVCF to VCF using GATK GenotypeGVCFs.
This is a key step in the GATK Best Practices germline short variant discovery workflow.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
from stargazer.utils import _run


@gatk_env.task
async def genotypegvcf(
    gvcf: Variants,
    ref: Reference,
) -> Variants:
    """
    Convert GVCF to VCF using GATK GenotypeGVCFs (joint genotyping).

    This tool applies GATK GenotypeGVCFs for joint genotyping,
    converting from g.vcf format to regular VCF format. This utilizes the
    HaplotypeCaller genotype likelihoods to produce final variant calls.

    For single-sample calling, this converts a sample's GVCF to final VCF.
    For multi-sample calling, first combine GVCFs using combinegvcfs, then
    run genotypegvcf on the combined GVCF.

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
        vcf = await genotypegvcf(gvcf=gvcf, ref=ref)

        # Multi-sample genotyping
        combined = await combinegvcfs(gvcfs=[gvcf1, gvcf2, gvcf3], ref=ref)
        joint_vcf = await genotypegvcf(gvcf=combined, ref=ref)

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037057852-GenotypeGVCFs
        https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
    """
    # Validate that this is a GVCF
    if not gvcf.is_gvcf:
        raise ValueError(
            f"genotypegvcf requires a GVCF file, but got VCF. vcf_name={gvcf.vcf_name}"
        )

    # Fetch all input files to cache
    await gvcf.fetch()
    await ref.fetch()

    # Get paths to input files
    ref_path = ref.get_ref_path()
    gvcf_path = gvcf.get_vcf_path()

    # Create output VCF path
    output_dir = ref_path.parent
    # Replace .g.vcf or .gvcf extension with .vcf
    vcf_basename = gvcf.vcf_name
    if vcf_basename.endswith(".g.vcf.gz"):
        vcf_basename = vcf_basename[:-9] + ".vcf"
    elif vcf_basename.endswith(".g.vcf"):
        vcf_basename = vcf_basename[:-6] + ".vcf"
    elif vcf_basename.endswith(".gvcf.gz"):
        vcf_basename = vcf_basename[:-8] + ".vcf"
    elif vcf_basename.endswith(".gvcf"):
        vcf_basename = vcf_basename[:-5] + ".vcf"
    else:
        # Fallback: append _genotyped.vcf
        vcf_basename = vcf_basename.rsplit(".", 1)[0] + "_genotyped.vcf"

    output_vcf = output_dir / vcf_basename

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

    # Create Variants object for output
    variants = Variants(
        sample_id=gvcf.sample_id,
        vcf_name=output_vcf.name,
    )

    # Build metadata for VCF file
    keyvalues = {
        "type": "variants",
        "sample_id": gvcf.sample_id,
        "caller": "genotypegvcf",
        "variant_type": "vcf",
        "source_caller": gvcf.caller,
    }

    # Try to get build from reference
    for f in ref.files:
        if f.name == ref.ref_name and "build" in f.keyvalues:
            keyvalues["build"] = f.keyvalues["build"]
            break

    # Upload VCF file to Pinata and add to variants
    await variants.add_files(file_paths=[output_vcf], keyvalues=keyvalues)

    return variants
