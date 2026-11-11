"""
### mark_duplicates task for Stargazer.

Marks duplicate reads in BAM files using GATK MarkDuplicates.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import Alignment, AlignmentIndex, DuplicateMetrics
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, temp_dir


@gatk_env.task
async def mark_duplicates(alignment: Alignment) -> Alignment:
    """
    Mark duplicate reads in a BAM file.

    Uses GATK MarkDuplicates to identify and tag duplicate reads that
    originated from the same DNA fragment (PCR or optical duplicates).
    Duplicates are marked with the 0x0400 SAM flag.

    Args:
        alignment: Input BAM asset (should be coordinate sorted)

    Returns:
        Alignment asset with duplicates marked, linked to its input alignment
        and reference

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037052812-MarkDuplicates-Picard
    """
    bam_path = await alignment.fetch()
    output_dir = temp_dir()

    output_bam = output_dir / f"{alignment.sample_id}_marked_duplicates.bam"
    metrics_file = output_dir / f"{alignment.sample_id}_duplicate_metrics.txt"

    cmd = [
        "gatk",
        "MarkDuplicates",
        "-I",
        str(bam_path),
        "-O",
        str(output_bam),
        "-M",
        str(metrics_file),
        "--CREATE_INDEX",
        "true",
    ]

    await run(cmd, cwd=str(output_dir))

    marked_bam = await Alignment.store(
        output_bam,
        sample_id=alignment.sample_id,
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=alignment.bqsr_applied,
        tool="gatk_mark_duplicates",
        reference_cid=alignment.reference_cid,
        source_cid=alignment.cid,
    )

    # Picard names the index <name>.bai, not <name>.bam.bai.
    bam_index = output_bam.with_suffix(".bai")
    await AlignmentIndex.store(
        bam_index,
        sample_id=alignment.sample_id,
        companion_of=marked_bam.cid,
    )

    if metrics_file.exists():
        await DuplicateMetrics.store(
            metrics_file,
            sample_id=alignment.sample_id,
            tool="gatk_mark_duplicates",
            alignment_cid=marked_bam.cid,
        )

    return marked_bam
