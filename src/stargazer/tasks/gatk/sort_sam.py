"""
### sort_sam task for Stargazer.

Sorts BAM files using GATK SortSam.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

import stargazer.utils.storage as _storage
from stargazer.assets import Alignment, AlignmentIndex
from stargazer.config import gatk_env, logger
from stargazer.utils import _run


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
        Alignment asset with sorted BAM file

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037056932-SortSam-Picard
    """
    logger.info(alignment.to_dict())
    valid_sort_orders = ["coordinate", "queryname", "duplicate"]
    if sort_order not in valid_sort_orders:
        raise ValueError(
            f"Invalid sort_order: {sort_order}. Must be one of {valid_sort_orders}"
        )

    bam_path = await alignment.fetch()
    output_dir = _storage.default_client.local_dir
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

    await _run(cmd, cwd=str(output_dir))

    if not output_bam.exists():
        raise FileNotFoundError(f"SortSam did not create output BAM at {output_bam}")

    sorted_bam = Alignment()
    await sorted_bam.update(
        output_bam,
        sample_id=alignment.sample_id,
        format="bam",
        sorted=sort_order,
        duplicates_marked=alignment.duplicates_marked,
        bqsr_applied=alignment.bqsr_applied,
        tool="gatk_sort_sam",
    )

    if sort_order == "coordinate":
        # Picard names the index <name>.bai, not <name>.bam.bai.
        bam_index = output_bam.with_suffix(".bai")
        if not bam_index.exists():
            raise FileNotFoundError(f"--CREATE_INDEX did not create {bam_index}")
        idx = AlignmentIndex()
        await idx.update(
            bam_index,
            sample_id=alignment.sample_id,
            alignment_cid=sorted_bam.cid,
        )

    logger.info(sorted_bam.to_dict())
    return sorted_bam
