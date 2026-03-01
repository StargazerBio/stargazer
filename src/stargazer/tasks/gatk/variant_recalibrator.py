"""
VariantRecalibrator task for Stargazer.

Builds a recalibration model to score variant quality for filtering purposes using VQSR.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
from stargazer.types.variants import RecalFile, TranchesFile
from stargazer.utils import _run


@gatk_env.task
async def variant_recalibrator(
    vcf: Variants,
    ref: Reference,
    resources: list[Variants],
    annotations: list[str],
    mode: str = "SNP",
    tranches: list[float] | None = None,
    max_gaussians: int = 8,
) -> Variants:
    """
    Build a recalibration model to score variant quality (VQSR).

    Uses machine learning to build a model that distinguishes true variants
    from artifacts based on variant annotations. Returns the same VCF with
    recal and tranches fields populated, ready to pass directly to apply_vqsr.

    Args:
        vcf: Input VCF with variants to recalibrate
        ref: Reference genome
        resources: List of Variants objects with VQSR metadata in vcf.keyvalues
        annotations: List of annotation names to use for training (e.g., ["QD", "FS", "MQ"])
        mode: Recalibration mode - "SNP", "INDEL", or "BOTH" (default: "SNP")
        tranches: Truth sensitivity tranches as percentages (default: [100.0, 99.9, 99.0, 90.0])
        max_gaussians: Maximum number of Gaussians for positive model (default: 8)

    Returns:
        Variants with recal and tranches fields set

    Raises:
        ValueError: If VCF is a GVCF (must be genotyped VCF)
        FileNotFoundError: If output files are not created

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037504732-VariantRecalibrator
    """
    if vcf.vcf and vcf.vcf.variant_type == "gvcf":
        raise ValueError(
            f"VariantRecalibrator requires a genotyped VCF, not a GVCF. "
            f"Run GenotypeGVCFs first. sample_id={vcf.sample_id}"
        )

    if not resources:
        raise ValueError("At least one VQSR resource must be provided")

    if not annotations:
        raise ValueError("At least one annotation must be provided")

    if mode not in ["SNP", "INDEL", "BOTH"]:
        raise ValueError(f"mode must be 'SNP', 'INDEL', or 'BOTH', got: {mode}")

    if tranches is None:
        tranches = [100.0, 99.9, 99.0, 90.0]

    await vcf.fetch()
    await ref.fetch()

    if not vcf.vcf or not vcf.vcf.path:
        raise ValueError("VCF file not available or not fetched")
    vcf_path = vcf.vcf.path
    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path
    output_dir = vcf_path.parent

    for resource in resources:
        await resource.fetch()

    recal_path = output_dir / f"{vcf.sample_id}.{mode.lower()}.recal"
    tranches_path = output_dir / f"{vcf.sample_id}.{mode.lower()}.tranches"

    cmd = [
        "gatk",
        "VariantRecalibrator",
        "-R",
        str(ref_path),
        "-V",
        str(vcf_path),
        "-O",
        str(recal_path),
        "--tranches-file",
        str(tranches_path),
        "--mode",
        mode,
        "--max-gaussians",
        str(max_gaussians),
    ]

    for resource in resources:
        resource_path = resource.vcf.path
        kv = resource.vcf.keyvalues
        resource_arg = (
            f"--resource:{resource.sample_id},known={kv.get('known')},"
            f"training={kv.get('training')},truth={kv.get('truth')},prior={kv.get('prior')}"
        )
        cmd.extend([resource_arg, str(resource_path)])

    for annotation in annotations:
        cmd.extend(["-an", annotation])

    for tranche in tranches:
        cmd.extend(["-tranche", str(tranche)])

    await _run(cmd, cwd=str(output_dir))

    if not recal_path.exists():
        raise FileNotFoundError(
            f"VariantRecalibrator did not create recal file at {recal_path}"
        )
    if not tranches_path.exists():
        raise FileNotFoundError(
            f"VariantRecalibrator did not create tranches file at {tranches_path}"
        )

    recal = RecalFile()
    await recal.update(recal_path, sample_id=vcf.sample_id, mode=mode.lower())

    tranches_comp = TranchesFile()
    await tranches_comp.update(
        tranches_path, sample_id=vcf.sample_id, mode=mode.lower()
    )

    return Variants(
        sample_id=vcf.sample_id,
        vcf=vcf.vcf,
        index=vcf.index,
        recal=recal,
        tranches=tranches_comp,
    )
