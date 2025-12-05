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
    # Download the reference directory
    await ref.dir.download()
    ref_file_path = ref.get_ref_path()

    # Verify the reference file exists
    if not ref_file_path.exists():
        raise FileNotFoundError(
            f"Reference file {ref.ref_name} not found in {ref.dir.path}"
        )

    # Run samtools faidx
    fai_path = Path(f"{ref_file_path}.fai")
    if fai_path.exists():
        return ref

    cmd = ["samtools", "faidx", ref_file_path, "--fai-idx", fai_path]
    await _run(cmd, cwd=ref.dir.path)

    return ref