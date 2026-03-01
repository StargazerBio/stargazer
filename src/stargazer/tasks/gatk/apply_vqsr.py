"""
ApplyVQSR task for Stargazer.

Applies a score cutoff to filter variants based on a recalibration table from VQSR.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
from stargazer.types.variants import VariantsFile
from stargazer.utils import _run


@gatk_env.task
async def apply_vqsr(
    vcf: Variants,
    ref: Reference | None = None,
    truth_sensitivity_filter_level: float = 99.0,
) -> Variants:
    """
    Apply VQSR filtering to variants based on recalibration model.

    Reads the recalibration model from vcf.recal and vcf.tranches (set by
    variant_recalibrator). Mode is read from vcf.recal.mode.

    Args:
        vcf: Variants with recal and tranches populated by variant_recalibrator
        ref: Reference genome (optional, not required for ApplyVQSR)
        truth_sensitivity_filter_level: Truth sensitivity level at which to filter
                                       (default: 99.0 for 99% sensitivity)

    Returns:
        Variants object with filtered VCF

    Raises:
        ValueError: If VCF is a GVCF or vcf.recal / vcf.tranches are not set
        FileNotFoundError: If output VCF is not created

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037056912-ApplyVQSR
    """
    if vcf.vcf and vcf.vcf.variant_type == "gvcf":
        raise ValueError(
            f"ApplyVQSR requires a genotyped VCF, not a GVCF. sample_id={vcf.sample_id}"
        )

    if not vcf.recal:
        raise ValueError("vcf.recal is not set. Run variant_recalibrator first.")
    if not vcf.tranches:
        raise ValueError("vcf.tranches is not set. Run variant_recalibrator first.")

    await vcf.fetch()
    if ref:
        await ref.fetch()

    if not vcf.vcf or not vcf.vcf.path:
        raise ValueError("VCF file not available or not fetched")
    vcf_path = vcf.vcf.path

    recal_path = vcf.recal.path
    if not recal_path or not recal_path.exists():
        raise FileNotFoundError(f"Recalibration file not found: {recal_path}")

    tranches_path = vcf.tranches.path
    if not tranches_path or not tranches_path.exists():
        raise FileNotFoundError(f"Tranches file not found: {tranches_path}")

    mode = vcf.recal.mode.upper()
    output_dir = vcf_path.parent
    output_vcf = output_dir / f"{vcf.sample_id}.{mode.lower()}.filtered.vcf"

    cmd = [
        "gatk",
        "ApplyVQSR",
        "-V",
        str(vcf_path),
        "-O",
        str(output_vcf),
        "--recal-file",
        str(recal_path),
        "--tranches-file",
        str(tranches_path),
        "--mode",
        mode,
        "--truth-sensitivity-filter-level",
        str(truth_sensitivity_filter_level),
    ]

    if ref:
        if not ref.fasta or not ref.fasta.path:
            raise ValueError("Reference FASTA file not available or not fetched")
        cmd.extend(["-R", str(ref.fasta.path)])

    await _run(cmd, cwd=str(output_dir))

    if not output_vcf.exists():
        raise FileNotFoundError(f"ApplyVQSR did not create output VCF at {output_vcf}")

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
