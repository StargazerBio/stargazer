"""
VariantRecalibrator task for Stargazer.

Builds a recalibration model to score variant quality for filtering purposes using VQSR.
"""

from pathlib import Path

from stargazer.config import gatk_env
from stargazer.types import Reference, Variants
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
) -> tuple[Path, Path]:
    """
    Build a recalibration model to score variant quality (VQSR).

    Uses machine learning to build a model that distinguishes true variants
    from artifacts based on variant annotations. This is the first step of
    VQSR filtering; use apply_vqsr to apply the model.

    Args:
        vcf: Input VCF with variants to recalibrate
        ref: Reference genome
        resources: List of Variants objects with VQSR metadata in vcf.keyvalues
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
        # Typical SNP recalibration — resources are Variants with VQSR keyvalues
        resources = [
            Variants(
                sample_id="hapmap",
                vcf=VariantsFile(
                    path=Path("hapmap_3.3.hg38.vcf.gz"),
                    keyvalues={"known": "false", "training": "true", "truth": "true", "prior": "15.0"},
                ),
            ),
            Variants(
                sample_id="dbsnp",
                vcf=VariantsFile(
                    path=Path("dbsnp_146.hg38.vcf.gz"),
                    keyvalues={"known": "true", "training": "false", "truth": "false", "prior": "2.0"},
                ),
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

    # Set default tranches
    if tranches is None:
        tranches = [100.0, 99.9, 99.0, 90.0]

    # Fetch inputs
    await vcf.fetch()
    await ref.fetch()

    # Get paths
    if not vcf.vcf or not vcf.vcf.path:
        raise ValueError("VCF file not available or not fetched")
    vcf_path = vcf.vcf.path
    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path
    output_dir = vcf_path.parent

    # Fetch resource files
    for resource in resources:
        await resource.fetch()

    # Output files (named by sample_id)
    recal_file = output_dir / f"{vcf.sample_id}.{mode.lower()}.recal"
    tranches_file = output_dir / f"{vcf.sample_id}.{mode.lower()}.tranches"

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
        resource_path = resource.vcf.path
        kv = resource.vcf.keyvalues
        resource_arg = (
            f"--resource:{resource.sample_id},known={kv.get('known')},"
            f"training={kv.get('training')},truth={kv.get('truth')},prior={kv.get('prior')}"
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
