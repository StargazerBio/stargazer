"""
BWA tasks for reference genome indexing and alignment.
"""

from stargazer.config import gatk_env
from stargazer.types import Alignment, Reads, Reference
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
        sorted_aligned = await sortsam(alignment=aligned, ref=ref, sort_order="coordinate")

    Reference:
        https://bio-bwa.sourceforge.net/bwa.shtml
    """
    # Fetch all input files to cache
    await reads.fetch()
    await ref.fetch()

    # Get paths to input files
    ref_path = ref.get_ref_path()
    r1_path = reads.get_r1_path()
    r2_path = reads.get_r2_path()

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

    # Create output BAM path in cache directory
    output_dir = ref_path.parent
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
    import subprocess

    # Construct full pipeline command
    bwa_cmd = " ".join([str(c) for c in cmd])
    samtools_cmd = f"samtools view -bS -o {output_bam} -"
    full_cmd = f"{bwa_cmd} | {samtools_cmd}"

    # Execute the pipeline
    proc = await subprocess.create_subprocess_shell(
        full_cmd,
        cwd=str(output_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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

    # Create Alignment object
    alignment = Alignment(
        sample_id=reads.sample_id,
        bam_name=output_bam.name,
    )

    # Build metadata for BAM file
    keyvalues = {
        "type": "alignment",
        "sample_id": reads.sample_id,
        "tool": "bwa_mem",
        "file_type": "bam",
        "sorted": "unsorted",  # BWA-MEM produces unsorted output
    }

    # Upload BAM file to Pinata and add to alignment
    await alignment.add_files(file_paths=[output_bam], keyvalues=keyvalues)

    return alignment
