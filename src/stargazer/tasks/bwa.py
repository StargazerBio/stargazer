"""
BWA tasks for reference genome indexing and alignment.
"""

from stargazer.types import Reference
from stargazer.config import pb_env
from stargazer.utils import _run


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
        raise FileNotFoundError(f"Reference file {ref.ref_name} not found in cache")

    # BWA index creates 5 files with these extensions
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]

    # Check if we already have all BWA index files in our files list
    index_file_names = [f"{ref.ref_name}{ext}" for ext in index_extensions]
    existing_names = {f.name for f in ref.files}

    if all(name in existing_names for name in index_file_names):
        return ref

    # Run bwa index in the cache directory
    # BWA index creates index files next to the source file
    cmd = ["bwa", "index", str(ref_file_path)]
    stdout, stderr = await _run(cmd, cwd=str(ref_file_path.parent))

    # Log any output from bwa
    if stdout:
        print(f"BWA stdout: {stdout}")
    if stderr:
        print(f"BWA stderr: {stderr}")

    # Get the reference file's metadata to copy over
    ref_file = None
    for f in ref.files:
        if f.name == ref.ref_name:
            ref_file = f
            break

    # Build metadata for index files
    keyvalues = {"type": "reference", "tool": "bwa_index"}
    if ref_file and ref_file.keyvalues:
        # Copy over build info if present
        if "build" in ref_file.keyvalues:
            keyvalues["build"] = ref_file.keyvalues["build"]

    # Collect all index file paths
    # BWA creates index files with the input filename as base
    # e.g., if input is /path/to/QmABC, it creates QmABC.amb, QmABC.ann, etc.
    base_name = ref_file_path.name
    index_file_paths = []

    for ext in index_extensions:
        # Index files are named after the cached file (CID), not ref_name
        cached_index_path = ref_file_path.parent / f"{base_name}{ext}"

        if not cached_index_path.exists():
            raise FileNotFoundError(
                f"BWA index file {cached_index_path.name} was not created"
            )

        index_file_paths.append(cached_index_path)

    # Upload all index files to Pinata and add to reference
    await ref.add_files(file_paths=index_file_paths, keyvalues=keyvalues)

    return ref
