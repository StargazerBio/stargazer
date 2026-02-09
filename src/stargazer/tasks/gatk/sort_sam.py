"""
sortsam task for Stargazer.

Sorts BAM files using GATK SortSam.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment
from stargazer.utils import _run


@gatk_env.task
async def sortsam(
    alignment: Alignment,
    ref: Reference,
    sort_order: str = "coordinate",
) -> Alignment:
    """
    Sort a SAM/BAM file.

    Uses GATK SortSam to sort reads by coordinate, queryname, or other
    properties.

    Args:
        alignment: Input BAM file to sort
        ref: Reference genome (required for working directory)
        sort_order: Sort order - one of "coordinate", "queryname", "duplicate"
                   Default: "coordinate"

    Returns:
        Alignment object with sorted BAM file

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")
        sorted_bam = await sortsam(
            alignment=alignment,
            ref=ref,
            sort_order="coordinate"
        )

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037056932-SortSam-Picard
    """
    valid_sort_orders = ["coordinate", "queryname", "duplicate"]
    if sort_order not in valid_sort_orders:
        raise ValueError(
            f"Invalid sort_order: {sort_order}. Must be one of {valid_sort_orders}"
        )

    # Fetch alignment and reference to cache
    await alignment.fetch()
    await ref.fetch()

    # Get paths
    if not ref.fasta or not ref.fasta.local_path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.local_path
    if not alignment.alignment or not alignment.alignment.local_path:
        raise ValueError("Alignment BAM file not available or not fetched")
    bam_path = alignment.alignment.local_path
    output_dir = ref_path.parent

    # Output BAM path
    output_bam = output_dir / f"{alignment.sample_id}_sorted_{sort_order}.bam"

    # Build GATK SortSam command
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

    # Create index for coordinate-sorted BAMs
    if sort_order == "coordinate":
        cmd.extend(["--CREATE_INDEX", "true"])

    # Execute SortSam
    await _run(cmd, cwd=str(output_dir))

    # Verify output was created
    if not output_bam.exists():
        raise FileNotFoundError(f"SortSam did not create output BAM at {output_bam}")

    # Create new Alignment object for sorted BAM
    sorted_alignment = Alignment(
        sample_id=alignment.sample_id,
    )

    # Upload sorted BAM to Pinata
    await sorted_alignment.update_alignment(
        output_bam,
        format="bam",
        is_sorted=(sort_order == "coordinate"),
        duplicates_marked=alignment.has_duplicates_marked,
        bqsr_applied=alignment.has_bqsr_applied,
        tool="gatk_sortsam",
    )

    # Upload index file if created
    if sort_order == "coordinate":
        bam_index = output_dir / f"{output_bam.name}.bai"
        if bam_index.exists():
            await sorted_alignment.update_index(bam_index)

    return sorted_alignment
