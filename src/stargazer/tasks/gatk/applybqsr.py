"""
applybqsr task for Stargazer.

Applies BQSR recalibration to BAM files using GATK ApplyBQSR.
"""

from stargazer.config import pb_env
from stargazer.types import Reference, Alignment
from stargazer.utils import _run
from stargazer.utils.pinata import IpFile, default_client


@pb_env.task
async def applybqsr(
    alignment: Alignment,
    ref: Reference,
    recal_report: IpFile,
) -> Alignment:
    """
    Apply Base Quality Score Recalibration to a BAM file.

    Uses GATK ApplyBQSR to recalibrate base quality scores using the
    recalibration table from baserecalibrator.

    This is the final step in GATK Best Practices data pre-processing before
    variant calling.

    Args:
        alignment: Input BAM file (sorted, duplicates marked)
        ref: Reference genome with FASTA index
        recal_report: BQSR recalibration report from baserecalibrator

    Returns:
        Alignment object with recalibrated BAM file

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")
        alignment = await mark_duplicates(alignment=alignment, ref=ref)
        recal_report = await baserecalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=["dbsnp_146.hg38.vcf.gz"],
        )
        recalibrated_bam = await applybqsr(
            alignment=alignment,
            ref=ref,
            recal_report=recal_report,
        )
        # recalibrated_bam is ready for variant calling

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037055712-ApplyBQSR
    """
    # Fetch all inputs to cache
    await alignment.fetch()
    await ref.fetch()
    await default_client.download_file(recal_report)

    # Get paths
    ref_path = ref.get_ref_path()
    bam_path = alignment.get_bam_path()
    recal_path = recal_report.local_path
    output_dir = ref_path.parent

    if not recal_path or not recal_path.exists():
        raise FileNotFoundError(
            "BQSR recalibration report not found in cache. "
            "Ensure recal_report was created by baserecalibrator."
        )

    # Output BAM path
    output_bam = output_dir / f"{alignment.sample_id}_recalibrated.bam"

    # Build GATK ApplyBQSR command
    cmd = [
        "gatk",
        "ApplyBQSR",
        "-R",
        str(ref_path),
        "-I",
        str(bam_path),
        "--bqsr-recal-file",
        str(recal_path),
        "-O",
        str(output_bam),
    ]

    # Execute ApplyBQSR
    await _run(cmd, cwd=str(output_dir))

    # Verify output was created
    if not output_bam.exists():
        raise FileNotFoundError(f"ApplyBQSR did not create output BAM at {output_bam}")

    # Create new Alignment object for recalibrated BAM
    recalibrated_alignment = Alignment(
        sample_id=alignment.sample_id,
        bam_name=output_bam.name,
    )

    # Build metadata for recalibrated BAM
    keyvalues = {
        "type": "alignment",
        "sample_id": alignment.sample_id,
        "tool": "gatk_applybqsr",
        "file_type": "bam",
        "sorted": "coordinate",
        "duplicates_marked": "true",
        "bqsr_applied": "true",
    }

    # Upload recalibrated BAM to Pinata
    await recalibrated_alignment.add_files(file_paths=[output_bam], keyvalues=keyvalues)

    return recalibrated_alignment
