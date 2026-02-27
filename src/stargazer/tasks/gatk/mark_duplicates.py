"""
mark_duplicates task for Stargazer.

Marks duplicate reads in BAM files using GATK MarkDuplicates.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile, AlignmentIndex
from stargazer.utils.component import ComponentFile
from stargazer.utils import _run
from stargazer.utils.storage import default_client


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
    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path
    if not alignment.alignment or not alignment.alignment.path:
        raise ValueError("Alignment BAM file not available or not fetched")
    bam_path = alignment.alignment.path
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

    # Upload marked BAM and build Alignment
    bam = AlignmentFile()
    await bam.update(
        output_bam,
        sample_id=alignment.sample_id,
        format="bam",
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=alignment.alignment.bqsr_applied,
        tool="gatk_mark_duplicates",
    )

    idx = None
    bam_index = output_dir / f"{output_bam.name}.bai"
    if bam_index.exists():
        idx = AlignmentIndex()
        await idx.update(bam_index, sample_id=alignment.sample_id)

    # Optionally upload metrics file
    if metrics_file.exists():
        metrics_comp = ComponentFile(
            path=metrics_file,
            keyvalues={
                "type": "duplicate_metrics",
                "sample_id": alignment.sample_id,
                "tool": "gatk_mark_duplicates",
            },
        )
        await default_client.upload(metrics_comp)

    return Alignment(sample_id=alignment.sample_id, alignment=bam, index=idx)
