"""
Flyte tasks for BWA (Burrows-Wheeler Aligner) genomics tools.

This module provides Flyte task wrappers for BWA tools:
- bwa_index: Index a reference genome for BWA alignment
"""

import asyncio
from pathlib import Path
from typing import Optional, List

import flyte
from flyte.io import File, Dir

from stargazer.types.reference import Reference
from stargazer.config import parabricks_env


async def run_bwa(
    subcommand: str,
    args: List[str],
    working_dir: Optional[Path] = None,
) -> tuple[int, str, str]:
    """
    Generic wrapper function to execute BWA commands.

    Args:
        subcommand: The BWA subcommand to run (e.g., 'index', 'mem')
        args: List of command-line arguments to pass to the subcommand
        working_dir: Optional working directory for the command

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd = ["bwa", subcommand] + args

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=working_dir,
    )

    stdout, stderr = await process.communicate()

    return (
        process.returncode,
        stdout.decode("utf-8") if stdout else "",
        stderr.decode("utf-8") if stderr else "",
    )


@parabricks_env.task
async def bwa_index(ref: File, algorithm: str = "bwtsw") -> Reference:
    """
    Create BWA index files for a reference genome.

    BWA index creates multiple index files (.amb, .ann, .bwt, .pac, .sa) required
    for alignment with BWA-MEM, BWA-ALN, and BWA-SW algorithms.

    Args:
        ref: Input FASTA reference file to index
        algorithm: Indexing algorithm - 'bwtsw' for large genomes (default), 'is' for small genomes,
                   'rb2' for Illumina reads. Use 'bwtsw' for human genomes.

    Returns:
        Reference object containing the FASTA and all BWA index files

    Notes:
        - Creates index files: .amb, .ann, .bwt, .pac, .sa
        - For genomes < 2GB, you can use algorithm='is'
        - For genomes > 2GB (e.g., human), use algorithm='bwtsw' (default)
    """
    # Download input file
    ref_local = await ref.download()
    ref_path = Path(ref_local)

    # Build command arguments
    args = []

    # Add algorithm if not default
    if algorithm != "bwtsw":
        args.extend(["-a", algorithm])

    # Add reference file
    args.append(ref_local)

    # Run bwa index
    returncode, stdout, stderr = await run_bwa("index", args)

    if returncode != 0:
        raise RuntimeError(f"bwa index failed with code {returncode}:\n{stderr}")

    # Verify index files were created
    # BWA creates: .amb, .ann, .bwt, .pac, .sa
    expected_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for ext in expected_extensions:
        index_file = Path(f"{ref_local}{ext}")
        if not index_file.exists():
            raise RuntimeError(f"Expected BWA index file {index_file} was not created")

    # Create reference directory with all files
    ref_dir_path = ref_path.parent / f"{ref_path.stem}_bwa_indexed"
    ref_dir_path.mkdir(exist_ok=True)

    # Copy reference and all index files to reference directory
    import shutil
    shutil.copy(ref_local, ref_dir_path / ref_path.name)

    for ext in expected_extensions:
        index_file = Path(f"{ref_local}{ext}")
        shutil.copy(index_file, ref_dir_path / f"{ref_path.name}{ext}")

    # Upload as directory
    ref_dir = await Dir.from_local(str(ref_dir_path))

    return Reference(
        ref_name=ref_path.name,
        index_name=ref_path.name,
        ref_dir=ref_dir,
    )


if __name__ == "__main__":
    # Example of how to run these tasks
    flyte.init_from_config()

    # Deploy the environment to make tasks available
    flyte.deploy(parabricks_env)
