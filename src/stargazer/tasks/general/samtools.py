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
    ref_file_path = ref.get_ref_path()

    # Verify the reference file exists
    if not ref_file_path.exists():
        raise FileNotFoundError(f"Reference file {ref.ref_name} not found in cache")

    # Check if we already have the .fai in our files list
    fai_name = f"{ref.ref_name}.fai"
    if any(f.name == fai_name for f in ref.files):
        return ref

    # Run samtools faidx in the cache directory
    # The .fai will be created next to the source file
    base_name = ref_file_path.name
    fai_path = ref_file_path.parent / f"{base_name}.fai"
    cmd = ["samtools", "faidx", str(ref_file_path), "--fai-idx", str(fai_path)]
    await _run(cmd, cwd=str(ref_file_path.parent))

    if not fai_path.exists():
        raise FileNotFoundError(f"FASTA index file {fai_path.name} was not created")

    # Get the reference file's metadata to copy over
    ref_file = None
    for f in ref.files:
        if f.name == ref.ref_name:
            ref_file = f
            break

    # Build metadata for index file
    keyvalues = {"type": "reference", "tool": "samtools_faidx"}
    if ref_file and ref_file.keyvalues:
        # Copy over build info if present
        if "build" in ref_file.keyvalues:
            keyvalues["build"] = ref_file.keyvalues["build"]

    # Upload .fai file to Pinata and add to reference
    await ref.add_files(file_paths=[fai_path], keyvalues=keyvalues)

    return ref
