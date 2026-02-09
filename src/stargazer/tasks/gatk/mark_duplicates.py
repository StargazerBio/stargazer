"""
mark_duplicates task for Stargazer.

Marks duplicate reads in BAM files using GATK MarkDuplicates.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment
from stargazer.utils import _run
from stargazer.utils.pinata import default_client


@gatk_env.task
async def mark_duplicates(
    alignment: Alignment,
    ref: Reference,
) -> Alignment:
    """
    Mark duplicate reads in a BAM file.

    Uses GATK MarkDuplicates to identify and tag duplicate reads that
    originated from the same DNA fragment (PCR or optical duplicates).
    Duplicates are marked with the 0x0400 SAM flag.

    Args:
        alignment: Input BAM file (should be coordinate sorted)
        ref: Reference genome with FASTA index

    Returns:
        Alignment object with duplicates marked

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")
        sorted_bam = await sort_sam(alignment=alignment, ref=ref, sort_order="coordinate")
        marked_bam = await mark_duplicates(alignment=sorted_bam, ref=ref)

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037052812-MarkDuplicates-Picard
    """
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

    # Output BAM and metrics paths
    output_bam = output_dir / f"{alignment.sample_id}_marked_duplicates.bam"
    metrics_file = output_dir / f"{alignment.sample_id}_duplicate_metrics.txt"

    # Build GATK MarkDuplicates command
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

    # Execute MarkDuplicates
    await _run(cmd, cwd=str(output_dir))

    # Verify output was created
    if not output_bam.exists():
        raise FileNotFoundError(
            f"MarkDuplicates did not create output BAM at {output_bam}"
        )

    # Create new Alignment object for marked BAM
    marked_alignment = Alignment(
        sample_id=alignment.sample_id,
    )

    # Upload marked BAM to Pinata
    await marked_alignment.update_alignment(
        output_bam,
        format="bam",
        is_sorted=True,
        duplicates_marked=True,
        bqsr_applied=alignment.has_bqsr_applied,
        tool="gatk_mark_duplicates",
    )

    # Upload index file
    bam_index = output_dir / f"{output_bam.name}.bai"
    if bam_index.exists():
        await marked_alignment.update_index(bam_index)

    # Optionally upload metrics file
    if metrics_file.exists():
        metrics_keyvalues = {
            "type": "duplicate_metrics",
            "sample_id": alignment.sample_id,
            "tool": "gatk_mark_duplicates",
        }
        await default_client.upload_file(metrics_file, keyvalues=metrics_keyvalues)

    return marked_alignment
