"""
### ApplyVQSR task for Stargazer.

Applies VQSR recalibration to a VCF using GATK ApplyVQSR.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import (
    Reference,
    Variants,
    VariantsIndex,
    VQSRModel,
    assemble,
)
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir

_DEFAULT_FILTER_LEVEL = {"SNP": 99.5, "INDEL": 99.0}


@gatk_env.task
async def apply_vqsr(
    vcf: Variants,
    ref: Reference,
    vqsr_model: VQSRModel,
    truth_sensitivity_filter_level: float | None = None,
) -> Variants:
    """
    Apply VQSR recalibration to a VCF using GATK ApplyVQSR.

    The recalibration mode (SNP or INDEL) is read from `vqsr_model.mode`.
    The recal file's index and the tranches file are the model's stored
    companions. If truth_sensitivity_filter_level is not provided, defaults
    to 99.5 for SNP and 99.0 for INDEL.

    Args:
        vcf: Raw (or SNP-filtered) VCF Variants asset
        ref: Reference FASTA asset
        vqsr_model: Recalibration model from variant_recalibrator
        truth_sensitivity_filter_level: VQSLOD filter threshold (optional)

    Returns:
        Variants asset with the VQSR-filtered VCF, linked to the input VCF

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360035531612-Variant-Quality-Score-Recalibration-VQSR
    """
    mode = vqsr_model.mode or "SNP"
    if mode not in ("SNP", "INDEL"):
        raise ValueError(f"VQSRModel mode must be 'SNP' or 'INDEL', got {mode!r}")

    filter_level = truth_sensitivity_filter_level or _DEFAULT_FILTER_LEVEL[mode]

    vcf_path = await vcf.fetch()
    ref_path = await ref.fetch()
    model_path = await vqsr_model.fetch()
    tranches = await assemble(asset="vqsr_tranches", companion_of=vqsr_model.cid)
    if not tranches:
        raise ValueError(f"VQSRModel {vqsr_model.cid} has no stored tranches file")
    tranches_path = await tranches[0].fetch()

    output_dir = scratch_dir()
    sample_id = vcf.sample_id or "cohort"
    output_vcf = output_dir / f"{sample_id}_vqsr_{mode.lower()}.vcf"

    cmd = [
        "gatk",
        "ApplyVQSR",
        "-R",
        str(ref_path),
        "-V",
        str(vcf_path),
        "--recal-file",
        str(model_path),
        "--tranches-file",
        str(tranches_path),
        "--truth-sensitivity-filter-level",
        str(filter_level),
        "--create-output-variant-index",
        "true",
        "-mode",
        mode,
        "-O",
        str(output_vcf),
    ]

    await run(cmd, cwd=str(output_dir))

    source_samples = vcf.source_samples or [sample_id]
    filtered_vcf = await Variants.store(
        output_vcf,
        sample_id=sample_id,
        caller="apply_vqsr",
        variant_type="vcf",
        vqsr_mode=mode,
        build=ref.build,
        source_samples=source_samples,
        source_cids=[vcf.cid],
    )

    idx_path = output_dir / f"{output_vcf.name}.idx"
    if idx_path.exists():
        await VariantsIndex.store(
            idx_path, sample_id=sample_id, companion_of=filtered_vcf.cid
        )

    return filtered_vcf
