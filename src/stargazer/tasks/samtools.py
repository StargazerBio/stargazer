"""
Samtools tasks for reference genome indexing.
"""
import tempfile
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
    # Initialize client if needed
    if not ref.client:
        from stargazer.utils.pinata import PinataClient
        ref.client = PinataClient()

    # Create a temporary working directory
    tmpdir = Path(tempfile.mkdtemp())

    try:
        # Download all reference files to temp directory
        for pinata_file in ref.files:
            file_path = await ref.client.download_file(pinata_file.cid)
            # Move to our working directory with the original name
            dest = tmpdir / pinata_file.name
            dest.write_bytes(Path(file_path).read_bytes())

        # Get the reference file path
        ref_file_path = tmpdir / ref.ref_name

        # Verify the reference file exists
        if not ref_file_path.exists():
            raise FileNotFoundError(
                f"Reference file {ref.ref_name} not found after download"
            )

        # Check if .fai already exists
        fai_path = Path(f"{ref_file_path}.fai")
        fai_name = f"{ref.ref_name}.fai"

        # Check if we already have the .fai in our files list
        if any(f.name == fai_name for f in ref.files):
            return ref

        # Run samtools faidx
        cmd = ["samtools", "faidx", str(ref_file_path), "--fai-idx", str(fai_path)]
        await _run(cmd, cwd=str(tmpdir))

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

    finally:
        # Cleanup temp directory
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)