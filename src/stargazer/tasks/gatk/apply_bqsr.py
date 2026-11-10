"""
### apply_bqsr task for Stargazer.

Applies BQSR recalibration to BAM files using GATK ApplyBQSR.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import Alignment, AlignmentIndex, BQSRReport, Reference
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir


@gatk_env.task
async def apply_bqsr(
    alignment: Alignment,
    ref: Reference,
    bqsr_report: BQSRReport,
) -> Alignment:
    """
    Apply Base Quality Score Recalibration to a BAM file.

    Args:
        alignment: Input BAM asset
        ref: Reference FASTA asset
        bqsr_report: Recalibration table from base_recalibrator

    Returns:
        Alignment asset with the recalibrated BAM, linked to its input
        alignment and reference; its index is stored as an AlignmentIndex

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037055712-ApplyBQSR
    """
    # fetch() auto-downloads companions (.fai, .dict, .bai, etc.)
    bam_path = await alignment.fetch()
    ref_path = await ref.fetch()
    recal_path = await bqsr_report.fetch()

    output_dir = scratch_dir()
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

    await run(cmd, cwd=str(output_dir))

    recal_bam = await Alignment.store(
        output_bam,
        sample_id=alignment.sample_id,
        sorted="coordinate",
        duplicates_marked=alignment.duplicates_marked,
        bqsr_applied=True,
        tool="gatk_apply_bqsr",
        reference_cid=ref.cid,
        source_cid=alignment.cid,
    )

    # GATK indexes its BAM output by default, naming it <name>.bai.
    bam_index = output_bam.with_suffix(".bai")
    await AlignmentIndex.store(
        bam_index,
        sample_id=alignment.sample_id,
        companion_of=recal_bam.cid,
    )

    return recal_bam
