"""
Samtools tasks for reference genome indexing.
"""
from pathlib import Path

import flyte
from flyte.io import Dir

from stargazer.types import Reference
from stargazer.config import pb_env
from stargazer.utils import _run


@pb_env.task
async def samtools_faidx(ref: Reference) -> Reference:
    """
    Create a FASTA index (.fai file) using samtools faidx.

    Args:
        ref: Reference object containing the FASTA file to index

    Returns:
        Reference object with the .fai index file added to the ref directory
    """
    # Download the reference directory if it's a Flyte Dir
    if isinstance(ref.dir, Dir):
        await ref.dir.download()

    # Get the reference file path
    ref_file_path = ref.get_ref_path()

    # Verify the reference file exists
    if not ref_file_path.exists():
        dir_path = ref.dir.path if isinstance(ref.dir, Dir) else str(ref.dir)
        raise FileNotFoundError(
            f"Reference file {ref.ref_name} not found in {dir_path}"
        )

    # Run samtools faidx
    fai_path = Path(f"{ref_file_path}.fai")
    if fai_path.exists():
        return ref

    # Get working directory for command execution
    cwd = ref.dir.path if isinstance(ref.dir, Dir) else str(ref.dir)
    cmd = ["samtools", "faidx", ref_file_path, "--fai-idx", fai_path]
    await _run(cmd, cwd=cwd)

    return ref