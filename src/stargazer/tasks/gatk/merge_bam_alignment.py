"""
### merge_bam_alignment task for Stargazer.

Merges aligned BAM with unmapped BAM using GATK MergeBamAlignment.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import Alignment, AlignmentIndex, Reference
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir


@gatk_env.task
async def merge_bam_alignment(
    aligned_bam: Alignment,
    unmapped_bam: Alignment,
    ref: Reference,
) -> Alignment:
    """
    Merge alignment data from aligned BAM with data in unmapped BAM.

    Args:
        aligned_bam: Aligned BAM asset from aligner
        unmapped_bam: Original unmapped BAM asset (must be queryname sorted)
        ref: Reference FASTA asset

    Returns:
        Alignment asset with the merged BAM, linked to the aligned BAM
        and reference

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037226472-MergeBamAlignment-Picard
    """
    # fetch() auto-downloads companions (.fai, .dict for ref)
    aligned_path = await aligned_bam.fetch()
    unmapped_path = await unmapped_bam.fetch()
    ref_path = await ref.fetch()

    output_dir = scratch_dir()
    output_bam = output_dir / f"{aligned_bam.sample_id}_merged.bam"

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
        "-1",
    ]

    await run(cmd, cwd=str(output_dir))

    merged_bam = await Alignment.store(
        output_bam,
        sample_id=aligned_bam.sample_id,
        sorted="coordinate",
        duplicates_marked=aligned_bam.duplicates_marked,
        bqsr_applied=aligned_bam.bqsr_applied,
        tool="gatk_merge_bam_alignment",
        reference_cid=ref.cid,
        source_cid=aligned_bam.cid,
    )

    # Picard names the index <name>.bai, not <name>.bam.bai.
    bam_index = output_bam.with_suffix(".bai")
    await AlignmentIndex.store(
        bam_index,
        sample_id=aligned_bam.sample_id,
        companion_of=merged_bam.cid,
    )

    return merged_bam
