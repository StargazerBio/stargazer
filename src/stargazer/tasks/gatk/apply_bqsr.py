"""
apply_bqsr task for Stargazer.

Applies BQSR recalibration to BAM files using GATK ApplyBQSR.
"""

import stargazer.utils.storage as _storage
from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile
from stargazer.utils import _run


@gatk_env.task
async def apply_bqsr(
    alignment: Alignment,
    ref: Reference,
) -> Alignment:
    """
    Apply Base Quality Score Recalibration to a BAM file.

    Uses GATK ApplyBQSR to recalibrate base quality scores using the
    recalibration table stored in alignment.bqsr_report (set by base_recalibrator).

    Args:
        alignment: Alignment with bqsr_report populated by base_recalibrator
        ref: Reference genome with FASTA index

    Returns:
        Alignment object with recalibrated BAM file

    Raises:
        ValueError: If alignment.bqsr_report is not set

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037055712-ApplyBQSR
    """
    if not alignment.bqsr_report:
        raise ValueError(
            "alignment.bqsr_report is not set. Run base_recalibrator first."
        )

    await alignment.fetch()
    await ref.fetch()

    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path

    if not alignment.alignment or not alignment.alignment.path:
        raise ValueError("Alignment BAM file not available or not fetched")
    bam_path = alignment.alignment.path

    recal_path = alignment.bqsr_report.path
    if not recal_path or not recal_path.exists():
        raise FileNotFoundError(
            "BQSR recalibration report not found in cache. "
            "Ensure alignment.bqsr_report was populated by base_recalibrator."
        )

    output_dir = _storage.default_client.local_dir
    output_bam = output_dir / f"{alignment.sample_id}_recalibrated.bam"

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

    await _run(cmd, cwd=str(output_dir))

    if not output_bam.exists():
        raise FileNotFoundError(f"ApplyBQSR did not create output BAM at {output_bam}")

    bam = AlignmentFile()
    await bam.update(
        output_bam,
        sample_id=alignment.sample_id,
        format="bam",
        sorted="coordinate",
        duplicates_marked=alignment.alignment.duplicates_marked,
        bqsr_applied=True,
        tool="gatk_apply_bqsr",
    )

    return Alignment(sample_id=alignment.sample_id, alignment=bam)
