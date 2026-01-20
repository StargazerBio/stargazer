"""
Samtools tasks for reference genome indexing.
"""

from stargazer.types import Reference
from stargazer.config import gatk_env
from stargazer.utils import _run


@gatk_env.task
async def samtools_faidx(ref: Reference) -> Reference:
    """
    Create a FASTA index (.fai file) using samtools faidx.

    Args:
        ref: Reference object containing the FASTA file to index

    Returns:
        Reference object with the .fai index file added
    """
    # Fetch all reference files to cache
    await ref.fetch()

    # Get the cached reference file path
    if not ref.fasta or not ref.fasta.local_path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_file_path = ref.fasta.local_path

    # Verify the reference file exists
    if not ref_file_path.exists():
        raise FileNotFoundError(f"Reference file {ref.build} not found in cache")

    # Check if we already have the .fai
    if ref.faidx is not None:
        return ref

    # Run samtools faidx in the cache directory
    # The .fai will be created next to the source file
    base_name = ref_file_path.name
    fai_path = ref_file_path.parent / f"{base_name}.fai"
    cmd = ["samtools", "faidx", str(ref_file_path), "--fai-idx", str(fai_path)]
    await _run(cmd, cwd=str(ref_file_path.parent))

    if not fai_path.exists():
        raise FileNotFoundError(f"FASTA index file {fai_path.name} was not created")

    # Upload .fai file to Pinata
    await ref.update_faidx(fai_path, build=ref.build, tool="samtools_faidx")

    return ref
