"""
merge_bam_alignment task for Stargazer.

Merges aligned BAM with unmapped BAM using GATK MergeBamAlignment.
"""

import stargazer.utils.storage as _storage
from stargazer.config import gatk_env
from stargazer.types import Alignment, AlignmentIndex, Reference
from stargazer.types.constellation import assemble
from stargazer.utils import _run


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
        Alignment asset with merged BAM file

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037226472-MergeBamAlignment-Picard
    """
    await _storage.default_client.download(aligned_bam)
    await _storage.default_client.download(unmapped_bam)
    await _storage.default_client.download(ref)

    # Download reference companions (.fai, .dict) — GATK requires them alongside FASTA
    c_ref = await assemble(
        reference_cid=ref.cid, asset=["reference_index", "sequence_dict"]
    )
    if c_ref._assets:
        await c_ref.fetch()

    ref_path = ref.path
    aligned_path = aligned_bam.path
    unmapped_path = unmapped_bam.path
    output_dir = _storage.default_client.local_dir
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

    await _run(cmd, cwd=str(output_dir))

    if not output_bam.exists():
        raise FileNotFoundError(
            f"MergeBamAlignment did not create output BAM at {output_bam}"
        )

    merged_bam = Alignment()
    await merged_bam.update(
        output_bam,
        sample_id=aligned_bam.sample_id,
        format="bam",
        sorted="coordinate",
        duplicates_marked=aligned_bam.duplicates_marked,
        bqsr_applied=aligned_bam.bqsr_applied,
        tool="gatk_merge_bam_alignment",
    )

    bam_index = output_dir / f"{output_bam.name}.bai"
    if bam_index.exists():
        idx = AlignmentIndex()
        await idx.update(
            bam_index,
            sample_id=aligned_bam.sample_id,
            alignment_cid=merged_bam.cid,
        )

    return merged_bam
