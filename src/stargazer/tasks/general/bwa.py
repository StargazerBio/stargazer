"""
BWA tasks for reference genome indexing and alignment.
"""

import asyncio
import shlex

import stargazer.utils.storage as _storage
from stargazer.config import gatk_env
from stargazer.types import Alignment, Reads, Reference
from stargazer.types.alignment import AlignmentFile
from stargazer.types.reference import AlignerIndex
from stargazer.utils import _run


@gatk_env.task
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
    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_file_path = ref.fasta.path

    # Verify the reference file exists
    if not ref_file_path.exists():
        raise FileNotFoundError(f"Reference file {ref.build} not found in cache")

    # BWA index creates 5 files with these extensions
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]

    # Check if we already have all BWA index files
    if len(ref.aligner_index) >= len(index_extensions):
        return ref

    # Run bwa index, directing output to output_dir via -p prefix
    output_dir = _storage.default_client.local_dir
    base_name = ref_file_path.name
    output_prefix = output_dir / base_name
    cmd = ["bwa", "index", "-p", str(output_prefix), str(ref_file_path)]
    stdout, stderr = await _run(cmd, cwd=str(output_dir))

    # Log any output from bwa
    if stdout:
        print(f"BWA stdout: {stdout}")
    if stderr:
        print(f"BWA stderr: {stderr}")

    # Get build from fasta metadata
    build = ref.fasta.build

    # Collect all index file paths from output_dir
    index_file_paths = []

    for ext in index_extensions:
        cached_index_path = output_dir / f"{base_name}{ext}"

        if not cached_index_path.exists():
            raise FileNotFoundError(
                f"BWA index file {cached_index_path.name} was not created"
            )

        index_file_paths.append(cached_index_path)

    # Upload all index files and add to reference
    for file_path in index_file_paths:
        idx = AlignerIndex()
        await idx.update(file_path, aligner="bwa", build=build)
        ref.aligner_index.append(idx)

    return ref


@gatk_env.task
async def bwa_mem(
    reads: Reads,
    ref: Reference,
    read_group: dict[str, str] | None = None,
) -> Alignment:
    """
    Align FASTQ reads to reference genome using BWA-MEM.

    Produces an unsorted SAM file that typically needs to be sorted
    before downstream processing (e.g., with SortSam).

    Args:
        reads: Input FASTQ files (paired-end or single-end)
        ref: Reference genome with BWA index and FAI
        read_group: Optional read group override (ID, SM, LB, PL, PU)
                   If not provided, defaults to SM=sample_id

    Returns:
        Alignment object with unsorted BAM file

    Example:
        from stargazer.tasks import hydrate

        ref_list = await hydrate({"type": "reference", "build": "GRCh38.fa"})
        ref = next((r for r in ref_list if isinstance(r, Reference)), None)
        reads_list = await hydrate({"type": "reads", "sample_id": "NA12829"})
        reads = next((r for r in reads_list if isinstance(r, Reads)), None)
        aligned = await bwa_mem(reads=reads, ref=ref)
        sorted_aligned = await sort_sam(alignment=aligned, ref=ref, sort_order="coordinate")

    Reference:
        https://bio-bwa.sourceforge.net/bwa.shtml
    """
    # Fetch all input files to cache
    await reads.fetch()
    await ref.fetch()

    # Get paths to input files
    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path

    if not reads.r1 or not reads.r1.path:
        raise ValueError("Reads R1 file not available or not fetched")
    r1_path = reads.r1.path

    r2_path = None
    if reads.r2 and reads.r2.path:
        r2_path = reads.r2.path

    # Build read group string
    # Required fields: ID, SM
    # Optional but recommended: LB (library), PL (platform), PU (platform unit)
    if read_group:
        # Ensure required fields are present
        rg = {"ID": reads.sample_id, "SM": reads.sample_id}
        rg.update(read_group)
        rg_parts = [f"{k}:{v}" for k, v in rg.items()]
        rg_string = "@RG\\t" + "\\t".join(rg_parts)
    else:
        # Default read group with sample ID
        rg_string = (
            f"@RG\\tID:{reads.sample_id}\\tSM:{reads.sample_id}\\tLB:lib\\tPL:ILLUMINA"
        )

    # Create output BAM path in output dir
    output_dir = _storage.default_client.local_dir
    output_bam = output_dir / f"{reads.sample_id}_aligned.bam"

    # Build BWA-MEM command
    # -K for reproducible results (process this many bases regardless of threads)
    # -R for read group
    # -t for threads (defaulting to 1, can be adjusted)
    cmd = [
        "bwa",
        "mem",
        "-K",
        "10000000",  # For reproducible results
        "-R",
        rg_string,
        "-t",
        "4",  # Use 4 threads
        str(ref_path),
    ]

    # Add FASTQ inputs
    if r2_path:
        # Paired-end
        cmd.extend([str(r1_path), str(r2_path)])
    else:
        # Single-end
        cmd.append(str(r1_path))

    # BWA-MEM outputs SAM to stdout, so we need to pipe to samtools to create BAM
    # Using bash -c to pipe bwa mem output through samtools view

    # Construct full pipeline command
    bwa_cmd = " ".join(shlex.quote(str(c)) for c in cmd)
    samtools_cmd = f"samtools view -bS -o {output_bam} -"
    full_cmd = f"{bwa_cmd} | {samtools_cmd}"

    # Execute the pipeline
    proc = await asyncio.create_subprocess_shell(
        full_cmd,
        cwd=str(output_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        stderr_text = stderr.decode() if stderr else ""
        stdout_text = stdout.decode() if stdout else ""
        raise RuntimeError(
            f"BWA-MEM failed with return code {proc.returncode}.\n"
            f"stdout: {stdout_text}\nstderr: {stderr_text}"
        )

    # Verify output BAM was created
    if not output_bam.exists():
        raise FileNotFoundError(f"BWA-MEM did not create output BAM at {output_bam}")

    # Upload BAM file and build Alignment
    bam = AlignmentFile()
    await bam.update(
        output_bam,
        sample_id=reads.sample_id,
        format="bam",
        duplicates_marked=False,
        bqsr_applied=False,
    )

    return Alignment(sample_id=reads.sample_id, alignment=bam)
