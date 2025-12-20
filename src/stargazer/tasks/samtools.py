"""
Samtools tasks for reference genome indexing.
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
    cmd = ["samtools", "faidx", str(ref_file_path), "--fai-idx", str(fai_path)]
    await _run(cmd, cwd=str(ref_file_path.parent))

    # Create an IpFile for the .fai (for now, just a local reference)
    # In production, you'd upload this to IPFS via Pinata
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