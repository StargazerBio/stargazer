"""
Tasks for reference genome indexing (samtools and bwa).
"""
from pathlib import Path
from datetime import datetime

from stargazer.types import Reference
from stargazer.config import pb_env
from stargazer.utils import _run
from stargazer.utils.pinata import IpFile


@pb_env.task
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
        raise FileNotFoundError(
            f"Reference file {ref.ref_name} not found in cache"
        )

    # Check if we already have the .fai in our files list
    fai_name = f"{ref.ref_name}.fai"
    if any(f.name == fai_name for f in ref.files):
        return ref

    # Run samtools faidx in the cache directory
    # The .fai will be created next to the source file
    fai_path = ref_file_path.parent / fai_name
    cmd = ["samtools", "faidx", ref_file_path, "--fai-idx", fai_path]
    await _run(cmd, cwd=str(ref_file_path.parent))

    # Create an IpFile for the .fai (for now, just a local reference)
    fai_file = IpFile(
        id="local",
        cid="local",  # Would be real CID after upload
        name=fai_name,
        size=fai_path.stat().st_size,
        keyvalues={},
        created_at=datetime.now(),
    )

    # Add the .fai file to the reference
    ref.files.append(fai_file)

    return ref


@pb_env.task
async def bwa_index(ref: Reference) -> Reference:
    """
    Create BWA index files for a reference genome using bwa index.

    Creates the following index files:
    - .amb (FASTA index file)
    - .ann (FASTA index file)
    - .bwt (BWT index)
    - .pac (Packed sequence)
    - .sa (Suffix array)

    Args:
        ref: Reference object containing the FASTA file to index

    Returns:
        Reference object with BWA index files added

    Reference:
        https://bio-bwa.sourceforge.net/bwa.shtml
    """
    # Fetch all reference files to cache
    await ref.fetch()

    # Get the cached reference file path
    ref_file_path = ref.get_ref_path()

    # Verify the reference file exists
    if not ref_file_path.exists():
        raise FileNotFoundError(
            f"Reference file {ref.ref_name} not found in cache"
        )

    # BWA index creates 5 files with these extensions
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]

    # Check if we already have all BWA index files in our files list
    index_file_names = [f"{ref.ref_name}{ext}" for ext in index_extensions]
    existing_names = {f.name for f in ref.files}

    if all(name in existing_names for name in index_file_names):
        return ref

    # Run bwa index in the cache directory
    # BWA index creates index files next to the source file
    cmd = ["bwa", "index", ref_file_path]
    await _run(cmd, cwd=str(ref_file_path.parent))

    # Add each index file to the reference
    for ext in index_extensions:
        index_name = f"{ref.ref_name}{ext}"
        index_path = ref_file_path.parent / index_name

        if not index_path.exists():
            raise FileNotFoundError(
                f"BWA index file {index_name} was not created"
            )

        # Create an IpFile for the index file
        index_file = IpFile(
            id="local",
            cid="local",  # Would be real CID after upload
            name=index_name,
            size=index_path.stat().st_size,
            keyvalues={},
            created_at=datetime.now(),
        )

        # Add the index file to the reference
        ref.files.append(index_file)

    return ref
