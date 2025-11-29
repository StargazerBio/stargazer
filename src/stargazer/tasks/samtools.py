"""
Flyte tasks for Samtools genomics utilities.

This module provides Flyte task wrappers for Samtools tools:
- faidx: Index FASTA files and extract subsequences
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

import flyte
from flyte.io import File


# Create task environment for Samtools
# Samtools doesn't require GPU resources
samtools_env = flyte.TaskEnvironment(
    name="samtools",
    image=flyte.Image.from_base("quay.io/biocontainers/samtools:1.21--h50ea8bc_0"),
    resources=flyte.Resources(
        cpu=4,
        memory="8Gi",
    ),
)


async def run_samtools(
    tool: str,
    args: List[str],
    working_dir: Optional[Path] = None,
) -> tuple[int, str, str]:
    """
    Generic wrapper function to execute samtools commands.

    Args:
        tool: The Samtools tool to run (e.g., 'faidx', 'index', 'view')
        args: List of command-line arguments to pass to the tool
        working_dir: Optional working directory for the command

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd = ["samtools", tool] + args

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


@dataclass
class FaidxOutputs:
    """Output files from samtools faidx tool."""
    fasta: File  # Input FASTA file (reference)
    fai: File  # FASTA index file (.fai)
    extracted_sequences: Optional[File] = None  # Extracted sequences (if regions specified)


@samtools_env.task
async def faidx(
    ref: File,
    regions: Optional[List[str]] = None,
    region_file: Optional[File] = None,
    output_path: Optional[str] = None,
    fai_idx_path: Optional[str] = None,
    length: Optional[int] = None,
    continue_on_error: bool = False,
    reverse_complement: bool = False,
    mark_strand: Optional[str] = None,
    write_index: bool = False,
    threads: int = 1,
) -> FaidxOutputs:
    """
    Run samtools faidx to index FASTA files or extract subsequences.

    If no regions are specified, this will index the FASTA file and create a .fai index.
    If regions are specified, it will extract those subsequences to a FASTA output file.

    Args:
        ref: Input FASTA file to index or query
        regions: List of regions to extract (format: 'chr:from-to' or 'chr')
        region_file: File containing regions to extract (one per line)
        output_path: Output file for extracted sequences (if extracting regions)
        fai_idx_path: Custom path for the .fai index file
        length: Length for FASTA sequence line wrapping (0 = no wrapping)
        continue_on_error: Continue if a non-existent region is requested
        reverse_complement: Output sequence as reverse complement
        mark_strand: Append strand indicator to sequence names ('rc', 'no', 'sign', or 'custom,<pos>,<neg>')
        write_index: Create index for output sequence data
        threads: Number of threads for compressed file operations

    Returns:
        FaidxOutputs with the FASTA file, index file, and optional extracted sequences

    Notes:
        - If no regions specified: Creates <ref>.fai index file
        - If regions specified: Extracts subsequences to output file
        - Input/output can be BGZF compressed (.gz, .bgz, .bgzf)
    """
    # Download input files
    ref_local = await ref.download()
    ref_path = Path(ref_local)

    # Build command arguments
    args = [ref_local]

    # Set index file path
    if fai_idx_path:
        index_path = fai_idx_path
    else:
        index_path = f"{ref_local}.fai"

    # Add regions from file if provided
    if region_file:
        region_file_local = await region_file.download()
        args.extend(["--region-file", region_file_local])

    # Add output file if specified or if regions are provided
    if regions or region_file:
        if not output_path:
            output_path = "extracted_sequences.fasta"
        args.extend(["--output", output_path])

    # Add optional arguments
    if fai_idx_path:
        args.extend(["--fai-idx", fai_idx_path])

    if length is not None:
        args.extend(["--length", str(length)])

    if continue_on_error:
        args.append("--continue")

    if reverse_complement:
        args.append("--reverse-complement")

    if mark_strand:
        args.extend(["--mark-strand", mark_strand])

    if write_index:
        args.append("--write-index")

    if threads > 1:
        args.extend(["--threads", str(threads - 1)])  # samtools uses extra threads

    # Add regions to extract (if specified)
    if regions:
        args.extend(regions)

    # Run the command
    returncode, stdout, stderr = await run_samtools("faidx", args)

    if returncode != 0:
        raise RuntimeError(f"samtools faidx failed with code {returncode}:\n{stderr}")

    # Upload output files
    fasta_file = await File.from_local(ref_local)

    # The index file
    if not Path(index_path).exists():
        raise RuntimeError(f"Expected index file {index_path} was not created")
    fai_file = await File.from_local(index_path)

    # Extracted sequences (if regions were specified)
    extracted_file = None
    if output_path and Path(output_path).exists():
        extracted_file = await File.from_local(output_path)

    return FaidxOutputs(
        fasta=fasta_file,
        fai=fai_file,
        extracted_sequences=extracted_file,
    )


if __name__ == "__main__":
    # Example of how to run these tasks
    flyte.init_from_config()

    # Deploy the environment to make tasks available
    flyte.deploy(samtools_env)
