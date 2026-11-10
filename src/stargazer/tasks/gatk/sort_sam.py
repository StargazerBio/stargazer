"""
### sort_sam task for Stargazer.

Sorts BAM files using GATK SortSam.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import Alignment, AlignmentIndex
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir


@gatk_env.task
async def sort_sam(
    alignment: Alignment,
    sort_order: str = "coordinate",
) -> Alignment:
    """
    Sort a SAM/BAM file.

    Args:
        alignment: Input BAM asset to sort
        sort_order: Sort order - one of "coordinate", "queryname", "duplicate"

    Returns:
        Alignment asset with the sorted BAM, linked to its input alignment
        and reference

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037056932-SortSam-Picard
    """
    valid_sort_orders = ["coordinate", "queryname", "duplicate"]
    if sort_order not in valid_sort_orders:
        raise ValueError(
            f"Invalid sort_order: {sort_order}. Must be one of {valid_sort_orders}"
        )

    bam_path = await alignment.fetch()
    output_dir = scratch_dir()
    output_bam = output_dir / f"{alignment.sample_id}_sorted_{sort_order}.bam"

    cmd = [
        "gatk",
        "SortSam",
        "-I",
        str(bam_path),
        "-O",
        str(output_bam),
        "--SORT_ORDER",
        sort_order,
    ]

    if sort_order == "coordinate":
        cmd.extend(["--CREATE_INDEX", "true"])

    await run(cmd, cwd=str(output_dir))

    sorted_bam = await Alignment.store(
        output_bam,
        sample_id=alignment.sample_id,
        sorted=sort_order,
        duplicates_marked=alignment.duplicates_marked,
        bqsr_applied=alignment.bqsr_applied,
        tool="gatk_sort_sam",
        reference_cid=alignment.reference_cid,
        source_cid=alignment.cid,
    )

    if sort_order == "coordinate":
        # Picard names the index <name>.bai, not <name>.bam.bai.
        bam_index = output_bam.with_suffix(".bai")
        await AlignmentIndex.store(
            bam_index,
            sample_id=alignment.sample_id,
            companion_of=sorted_bam.cid,
        )

    return sorted_bam
