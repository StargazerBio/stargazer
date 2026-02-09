"""
CombineGVCFs task for Stargazer.

Combines multiple per-sample GVCFs into a single multi-sample GVCF
for joint genotyping using GATK CombineGVCFs.

This is a key step in the GATK Best Practices germline short variant discovery
workflow when performing cohort analysis.
"""

from pathlib import Path

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
from stargazer.utils import _run


@gatk_env.task
async def combine_gvcfs(
    gvcfs: list[Variants],
    ref: Reference,
    cohort_id: str = "cohort",
) -> Variants:
    """
    Combine multiple per-sample GVCFs into a single multi-sample GVCF.

    Uses GATK CombineGVCFs to merge GVCFs from multiple samples into a single
    GVCF that can be used for joint genotyping with GenotypeGVCFs.

    Note: CombineGVCFs is suitable for small cohorts (< 100 samples).
    For larger cohorts, GenomicsDBImport is recommended but requires more
    complex setup.

    Args:
        gvcfs: List of Variants objects, each containing a GVCF from a single sample
        ref: Reference genome used for variant calling
        cohort_id: Identifier for the combined cohort (default: "cohort")

    Returns:
        Variants object with combined multi-sample GVCF

    Raises:
        ValueError: If any input is not a GVCF, or if list is empty
        FileNotFoundError: If combining fails to produce output

    Example:
        # Generate per-sample GVCFs
        gvcf1 = await haplotypecaller(alignment1, ref, output_gvcf=True)
        gvcf2 = await haplotypecaller(alignment2, ref, output_gvcf=True)
        gvcf3 = await haplotypecaller(alignment3, ref, output_gvcf=True)

        # Combine GVCFs
        combined = await combine_gvcfs(
            gvcfs=[gvcf1, gvcf2, gvcf3],
            ref=ref,
            cohort_id="family_study"
        )

        # Joint genotyping
        joint_vcf = await genotype_gvcf(gvcf=combined, ref=ref)

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels
        https://gatk.broadinstitute.org/hc/en-us/articles/360037053272-CombineGVCFs
    """
    # Validate inputs
    if not gvcfs:
        raise ValueError("gvcfs list cannot be empty")

    # Validate all inputs are GVCFs
    for i, gvcf in enumerate(gvcfs):
        if not gvcf.is_gvcf:
            raise ValueError(
                f"combine_gvcfs requires GVCF files, but gvcfs[{i}] is VCF. "
                f"sample_id={gvcf.sample_id}"
            )

    # Fetch all input files to cache
    await ref.fetch()
    gvcf_paths: list[Path] = []
    sample_ids: list[str] = []

    for gvcf in gvcfs:
        await gvcf.fetch()
        if not gvcf.vcf or not gvcf.vcf.local_path:
            raise ValueError(f"GVCF file not available for sample_id={gvcf.sample_id}")
        gvcf_paths.append(gvcf.vcf.local_path)
        sample_ids.append(gvcf.sample_id)

    # Get reference path
    if not ref.fasta or not ref.fasta.local_path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.local_path

    # Create output GVCF path
    output_dir = ref_path.parent
    output_gvcf = output_dir / f"{cohort_id}_combined.g.vcf"

    # Build CombineGVCFs command
    # Note: Using GATK directly since Parabricks doesn't have a GPU-accelerated version
    # CombineGVCFs is I/O bound, not compute bound, so GPU acceleration has minimal benefit
    cmd = [
        "gatk",
        "CombineGVCFs",
        "-R",
        str(ref_path),
        "-O",
        str(output_gvcf),
    ]

    # Add all input GVCFs
    for gvcf_path in gvcf_paths:
        cmd.extend(["-V", str(gvcf_path)])

    # Execute CombineGVCFs
    stdout, stderr = await _run(cmd, cwd=str(output_dir))

    # Verify output GVCF was created
    if not output_gvcf.exists():
        raise FileNotFoundError(
            f"CombineGVCFs did not create output GVCF at {output_gvcf}. "
            f"stderr: {stderr}"
        )

    # Create Variants object for combined GVCF
    # Use cohort_id as sample_id for multi-sample GVCFs
    combined = Variants(
        sample_id=cohort_id,
    )

    # Build metadata for combined GVCF
    build = (
        ref.fasta.keyvalues.get("build") if ref.fasta and ref.fasta.keyvalues else None
    )
    await combined.update_vcf(
        output_gvcf,
        caller="combine_gvcfs",
        variant_type="gvcf",
        build=build,
        sample_count=len(sample_ids),
        source_samples=sample_ids,
    )

    return combined
