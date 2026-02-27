"""
ApplyVQSR task for Stargazer.

Applies a score cutoff to filter variants based on a recalibration table from VQSR.
"""

from pathlib import Path

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
from stargazer.types.variants import VariantsFile
from stargazer.utils import _run


@gatk_env.task
async def apply_vqsr(
    vcf: Variants,
    recal_file: Path,
    tranches_file: Path,
    ref: Reference | None = None,
    mode: str = "SNP",
    truth_sensitivity_filter_level: float = 99.0,
) -> Variants:
    """
    Apply VQSR filtering to variants based on recalibration model.

    This tool applies the recalibration model built by VariantRecalibrator
    to filter variants. Variants passing the specified truth sensitivity
    threshold will be marked as PASS, while others will be filtered.

    Args:
        vcf: Input VCF with variants to filter
        recal_file: Recalibration file from VariantRecalibrator (.recal)
        tranches_file: Tranches file from VariantRecalibrator (.tranches)
        ref: Reference genome (optional, not required for ApplyVQSR)
        mode: Recalibration mode - "SNP", "INDEL", or "BOTH" (default: "SNP")
        truth_sensitivity_filter_level: Truth sensitivity level at which to filter
                                       (default: 99.0 for 99% sensitivity)

    Returns:
        Variants object with filtered VCF

    Raises:
        ValueError: If VCF is a GVCF (must be genotyped VCF)
        FileNotFoundError: If output VCF is not created

    Example:
        # After running VariantRecalibrator
        recal, tranches = await variant_recalibrator(
            vcf=joint_vcf,
            ref=ref,
            resources=snp_resources,
            annotations=snp_annotations,
            mode="SNP",
        )

        # Apply the recalibration
        filtered_vcf = await apply_vqsr(
            vcf=joint_vcf,
            recal_file=recal,
            tranches_file=tranches,
            mode="SNP",
            truth_sensitivity_filter_level=99.0,
        )

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037056912-ApplyVQSR
        https://gatk.broadinstitute.org/hc/en-us/articles/360035531612-Variant-Quality-Score-Recalibration-VQSR
    """
    # Validate inputs
    if vcf.vcf and vcf.vcf.variant_type == "gvcf":
        raise ValueError(
            f"ApplyVQSR requires a genotyped VCF, not a GVCF. sample_id={vcf.sample_id}"
        )

    if mode not in ["SNP", "INDEL", "BOTH"]:
        raise ValueError(f"mode must be 'SNP', 'INDEL', or 'BOTH', got: {mode}")

    if not recal_file.exists():
        raise FileNotFoundError(f"Recalibration file not found: {recal_file}")

    if not tranches_file.exists():
        raise FileNotFoundError(f"Tranches file not found: {tranches_file}")

    # Fetch inputs
    await vcf.fetch()
    if ref:
        await ref.fetch()

    # Get paths
    if not vcf.vcf or not vcf.vcf.path:
        raise ValueError("VCF file not available or not fetched")
    vcf_path = vcf.vcf.path
    output_dir = vcf_path.parent

    # Output VCF
    output_vcf = output_dir / f"{vcf.sample_id}.{mode.lower()}.filtered.vcf"

    # Build command
    cmd = [
        "gatk",
        "ApplyVQSR",
        "-V",
        str(vcf_path),
        "-O",
        str(output_vcf),
        "--recal-file",
        str(recal_file),
        "--tranches-file",
        str(tranches_file),
        "--mode",
        mode,
        "--truth-sensitivity-filter-level",
        str(truth_sensitivity_filter_level),
    ]

    # Add reference if provided (optional for ApplyVQSR)
    if ref:
        if not ref.fasta or not ref.fasta.path:
            raise ValueError("Reference FASTA file not available or not fetched")
        cmd.extend(["-R", str(ref.fasta.path)])

    # Execute
    await _run(cmd, cwd=str(output_dir))

    # Verify output
    if not output_vcf.exists():
        raise FileNotFoundError(f"ApplyVQSR did not create output VCF at {output_vcf}")

    # Upload filtered VCF and build Variants
    vcf_comp = VariantsFile()
    await vcf_comp.update(
        output_vcf,
        sample_id=vcf.sample_id,
        caller=vcf.vcf.caller,
        variant_type="vcf_filtered",
        filter_method="vqsr",
        vqsr_mode=mode.lower(),
        truth_sensitivity=str(truth_sensitivity_filter_level),
        build=vcf.vcf.build,
    )

    return Variants(sample_id=vcf.sample_id, vcf=vcf_comp)
