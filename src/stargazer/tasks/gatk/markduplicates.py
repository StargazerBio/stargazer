"""
markduplicates task for Stargazer.

Marks duplicate reads in BAM files using GATK MarkDuplicates.
"""

from stargazer.config import pb_env
from stargazer.types import Reference, Alignment
from stargazer.utils import _run
from stargazer.utils.pinata import default_client


@pb_env.task
async def markduplicates(
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
        sorted_bam = await sortsam(alignment=alignment, ref=ref, sort_order="coordinate")
        marked_bam = await markduplicates(alignment=sorted_bam, ref=ref)

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037052812-MarkDuplicates-Picard
    """
    # Fetch alignment and reference to cache
    await alignment.fetch()
    await ref.fetch()

    # Get paths
    ref_path = ref.get_ref_path()
    bam_path = alignment.get_bam_path()
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
        bam_name=output_bam.name,
    )

    # Build metadata for marked BAM
    keyvalues = {
        "type": "alignment",
        "sample_id": alignment.sample_id,
        "tool": "gatk_markduplicates",
        "file_type": "bam",
        "sorted": "coordinate",
        "duplicates_marked": "true",
    }

    # Collect output files (BAM and index)
    output_files = [output_bam]
    bam_index = output_dir / f"{output_bam.name}.bai"
    if bam_index.exists():
        output_files.append(bam_index)

    # Upload marked BAM to Pinata
    await marked_alignment.add_files(file_paths=output_files, keyvalues=keyvalues)

    # Optionally upload metrics file
    if metrics_file.exists():
        metrics_keyvalues = {
            "type": "duplicate_metrics",
            "sample_id": alignment.sample_id,
            "tool": "gatk_markduplicates",
        }
        await default_client.upload_file(metrics_file, keyvalues=metrics_keyvalues)

    return marked_alignment
