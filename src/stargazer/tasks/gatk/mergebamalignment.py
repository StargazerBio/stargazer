"""
mergebamalignment task for Stargazer.

Merges aligned BAM with unmapped BAM using GATK MergeBamAlignment.
"""

from stargazer.config import pb_env
from stargazer.types import Reference, Alignment
from stargazer.utils import _run


@pb_env.task
async def mergebamalignment(
    aligned_bam: Alignment,
    unmapped_bam: Alignment,
    ref: Reference,
) -> Alignment:
    """
    Merge alignment data from aligned BAM with data in unmapped BAM.

    Uses GATK MergeBamAlignment to merge BAM alignment info from an aligner
    with the data in an unmapped BAM file, producing a BAM file that has
    alignment data and all remaining data from the unmapped BAM (metadata,
    read-level tags, etc).

    Args:
        aligned_bam: Aligned BAM file from aligner
        unmapped_bam: Original unmapped BAM file (must be queryname sorted)
        ref: Reference genome with FASTA index

    Returns:
        Alignment object with merged BAM file

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")
        merged_bam = await mergebamalignment(
            aligned_bam=aligned,
            unmapped_bam=unmapped,
            ref=ref
        )

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037226472-MergeBamAlignment-Picard
    """
    # Fetch all inputs to cache
    await aligned_bam.fetch()
    await unmapped_bam.fetch()
    await ref.fetch()

    # Get paths
    ref_path = ref.get_ref_path()
    aligned_path = aligned_bam.get_bam_path()
    unmapped_path = unmapped_bam.get_bam_path()
    output_dir = ref_path.parent

    # Output BAM path
    output_bam = output_dir / f"{aligned_bam.sample_id}_merged.bam"

    # Build GATK MergeBamAlignment command
    cmd = [
        "gatk",
        "MergeBamAlignment",
        "-R",
        str(ref_path),
        "-ALIGNED",
        str(aligned_path),
        "-UNMAPPED",
        str(unmapped_path),
        "-O",
        str(output_bam),
        "--SORT_ORDER",
        "coordinate",
        "--CREATE_INDEX",
        "true",
        "--ADD_MATE_CIGAR",
        "true",
        "--CLIP_ADAPTERS",
        "true",
        "--CLIP_OVERLAPPING_READS",
        "true",
        "--INCLUDE_SECONDARY_ALIGNMENTS",
        "true",
        "--MAX_INSERTIONS_OR_DELETIONS",
        "-1",  # Allow any number of indels
    ]

    # Execute MergeBamAlignment
    await _run(cmd, cwd=str(output_dir))

    # Verify output was created
    if not output_bam.exists():
        raise FileNotFoundError(
            f"MergeBamAlignment did not create output BAM at {output_bam}"
        )

    # Create new Alignment object for merged BAM
    merged_alignment = Alignment(
        sample_id=aligned_bam.sample_id,
        bam_name=output_bam.name,
    )

    # Build metadata for merged BAM
    keyvalues = {
        "type": "alignment",
        "sample_id": aligned_bam.sample_id,
        "tool": "gatk_mergebamalignment",
        "file_type": "bam",
        "sorted": "coordinate",
    }

    # Collect output files (BAM and index)
    output_files = [output_bam]
    bam_index = output_dir / f"{output_bam.name}.bai"
    if bam_index.exists():
        output_files.append(bam_index)

    # Upload merged BAM to Pinata
    await merged_alignment.add_files(file_paths=output_files, keyvalues=keyvalues)

    return merged_alignment
