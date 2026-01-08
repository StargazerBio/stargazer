"""
DeepVariant task for Stargazer.

Calls germline variants from aligned BAM using Google DeepVariant neural network.
"""

from stargazer.config import pb_env
from stargazer.types import Reference, Alignment, Variants
from stargazer.utils import _run


@pb_env.task
async def deepvariant(
    alignment: Alignment,
    ref: Reference,
    output_gvcf: bool = False,
) -> Variants:
    """
    Call variants from aligned BAM using DeepVariant.

    Uses Parabricks DeepVariant (GPU-accelerated Google DeepVariant).

    Args:
        alignment: Input BAM file (sorted, duplicate-marked)
        ref: Reference genome with FAI index
        output_gvcf: Whether to output GVCF format (default: False)

    Returns:
        Variants object with VCF/GVCF variant calls

    Example:
        alignment = await fq2bam(reads=reads, ref=ref)
        variants = await deepvariant(alignment=alignment, ref=ref)

    Reference:
        https://docs.nvidia.com/clara/parabricks/latest/documentation/tooldocs/man_deepvariant.html
    """
    # Fetch all input files to cache
    await alignment.fetch()
    await ref.fetch()

    # Get paths to input files
    ref_path = ref.get_ref_path()
    bam_path = alignment.get_bam_path()

    # Create output VCF path in a temporary directory
    output_dir = ref_path.parent
    vcf_ext = "g.vcf" if output_gvcf else "vcf"
    output_vcf = output_dir / f"{alignment.sample_id}_deepvariant.{vcf_ext}"

    # Build deepvariant command
    cmd = [
        "pbrun",
        "deepvariant",
        "--ref",
        str(ref_path),
        "--in-bam",
        str(bam_path),
        "--out-variants",
        str(output_vcf),
    ]

    # Add GVCF flag if requested
    if output_gvcf:
        cmd.append("--gvcf")

    # Execute deepvariant
    stdout, stderr = await _run(cmd, cwd=str(output_dir))

    # Verify output VCF was created
    if not output_vcf.exists():
        raise FileNotFoundError(
            f"deepvariant did not create output VCF at {output_vcf}. stderr: {stderr}"
        )

    # Create Variants object first, then add files to trigger upload
    variants = Variants(
        sample_id=alignment.sample_id,
        vcf_name=output_vcf.name,
    )

    # Build metadata for VCF file
    keyvalues = {
        "type": "variants",
        "sample_id": alignment.sample_id,
        "caller": "deepvariant",
        "variant_type": "gvcf" if output_gvcf else "vcf",
    }

    # Try to get build from reference
    for f in ref.files:
        if f.name == ref.ref_name and "build" in f.keyvalues:
            keyvalues["build"] = f.keyvalues["build"]
            break

    # Upload VCF file to Pinata and add to variants
    await variants.add_files(file_paths=[output_vcf], keyvalues=keyvalues)

    return variants
