"""
VariantRecalibrator task for Stargazer.

Builds a recalibration model to score variant quality for filtering purposes using VQSR.
"""

from dataclasses import dataclass
from pathlib import Path

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
from stargazer.utils import _run


@dataclass
class VQSRResource:
    """
    Resource file for VQSR training/validation.

    Attributes:
        name: Resource name label (e.g., "hapmap", "1000G", "dbsnp")
        vcf_name: Name of the resource VCF file (stored in Pinata)
        known: Whether the resource is a known site (true/false string for GATK)
        training: Whether to use for training the model (true/false string)
        truth: Whether this is a truth set (true/false string)
        prior: Prior probability for variants in this resource (e.g., "15.0" for high confidence)

    Example:
        hapmap = VQSRResource(
            name="hapmap",
            vcf_name="hapmap_3.3.hg38.vcf.gz",
            known="false",
            training="true",
            truth="true",
            prior="15.0"
        )
    """

    name: str
    vcf_name: str
    known: str
    training: str
    truth: str
    prior: str


@gatk_env.task
async def variant_recalibrator(
    vcf: Variants,
    ref: Reference,
    resources: list[VQSRResource],
    annotations: list[str],
    mode: str = "SNP",
    tranches: list[float] | None = None,
    max_gaussians: int = 8,
) -> tuple[Path, Path]:
    """
    Build a recalibration model to score variant quality (VQSR).

    Uses machine learning to build a model that distinguishes true variants
    from artifacts based on variant annotations. This is the first step of
    VQSR filtering; use apply_vqsr to apply the model.

    Args:
        vcf: Input VCF with variants to recalibrate
        ref: Reference genome
        resources: List of VQSRResource objects specifying training/truth sets
        annotations: List of annotation names to use for training (e.g., ["QD", "FS", "MQ"])
        mode: Recalibration mode - "SNP", "INDEL", or "BOTH" (default: "SNP")
        tranches: Truth sensitivity tranches as percentages (default: [100.0, 99.9, 99.0, 90.0])
        max_gaussians: Maximum number of Gaussians for positive model (default: 8)

    Returns:
        Tuple of (recal_file, tranches_file) paths

    Raises:
        ValueError: If VCF is a GVCF (must be genotyped VCF)
        FileNotFoundError: If output files are not created

    Example:
        # Typical SNP recalibration
        resources = [
            VQSRResource(
                name="hapmap",
                vcf_name="hapmap_3.3.hg38.vcf.gz",
                known="false", training="true", truth="true", prior="15.0"
            ),
            VQSRResource(
                name="omni",
                vcf_name="1000G_omni2.5.hg38.vcf.gz",
                known="false", training="true", truth="true", prior="12.0"
            ),
            VQSRResource(
                name="1000G",
                vcf_name="1000G_phase1.snps.high_confidence.hg38.vcf.gz",
                known="false", training="true", truth="false", prior="10.0"
            ),
            VQSRResource(
                name="dbsnp",
                vcf_name="dbsnp_146.hg38.vcf.gz",
                known="true", training="false", truth="false", prior="2.0"
            ),
        ]

        annotations = ["QD", "MQRankSum", "ReadPosRankSum", "FS", "MQ", "SOR"]

        recal, tranches = await variant_recalibrator(
            vcf=joint_vcf,
            ref=ref,
            resources=resources,
            annotations=annotations,
            mode="SNP",
        )

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037504732-VariantRecalibrator
        https://gatk.broadinstitute.org/hc/en-us/articles/360035531612-Variant-Quality-Score-Recalibration-VQSR
    """

    # Validate inputs
    if vcf.is_gvcf:
        raise ValueError(
            f"VariantRecalibrator requires a genotyped VCF, not a GVCF. "
            f"Run GenotypeGVCFs first. vcf_name={vcf.vcf_name}"
        )

    if not resources:
        raise ValueError("At least one VQSR resource must be provided")

    if not annotations:
        raise ValueError("At least one annotation must be provided")

    if mode not in ["SNP", "INDEL", "BOTH"]:
        raise ValueError(f"mode must be 'SNP', 'INDEL', or 'BOTH', got: {mode}")

    # Set default tranches
    if tranches is None:
        tranches = [100.0, 99.9, 99.0, 90.0]

    # Fetch inputs
    await vcf.fetch()
    await ref.fetch()

    # Get paths
    vcf_path = vcf.get_vcf_path()
    ref_path = ref.get_ref_path()
    output_dir = vcf_path.parent

    # Fetch resource files
    for resource in resources:
        # Resources should be pre-uploaded to Pinata and hydrated like any other file
        # For now, assume they're in the same output_dir
        resource_path = output_dir / resource.vcf_name
        if not resource_path.exists():
            raise FileNotFoundError(
                f"Resource file not found: {resource_path}. "
                f"Please ensure VQSR resources are available."
            )

    # Output files
    recal_file = output_dir / f"{vcf.vcf_name.rsplit('.', 1)[0]}.{mode.lower()}.recal"
    tranches_file = (
        output_dir / f"{vcf.vcf_name.rsplit('.', 1)[0]}.{mode.lower()}.tranches"
    )

    # Build command
    cmd = [
        "gatk",
        "VariantRecalibrator",
        "-R",
        str(ref_path),
        "-V",
        str(vcf_path),
        "-O",
        str(recal_file),
        "--tranches-file",
        str(tranches_file),
        "--mode",
        mode,
        "--max-gaussians",
        str(max_gaussians),
    ]

    # Add resources
    for resource in resources:
        resource_path = output_dir / resource.vcf_name
        resource_arg = (
            f"--resource:{resource.name},known={resource.known},"
            f"training={resource.training},truth={resource.truth},prior={resource.prior}"
        )
        cmd.extend([resource_arg, str(resource_path)])

    # Add annotations
    for annotation in annotations:
        cmd.extend(["-an", annotation])

    # Add tranches
    for tranche in tranches:
        cmd.extend(["-tranche", str(tranche)])

    # Execute
    await _run(cmd, cwd=str(output_dir))

    # Verify outputs
    if not recal_file.exists():
        raise FileNotFoundError(
            f"VariantRecalibrator did not create recal file at {recal_file}"
        )
    if not tranches_file.exists():
        raise FileNotFoundError(
            f"VariantRecalibrator did not create tranches file at {tranches_file}"
        )

    return recal_file, tranches_file
