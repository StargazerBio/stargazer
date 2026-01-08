"""
fq2bam task for Stargazer.

Aligns FASTQ reads to reference genome, sorts, and marks duplicates using Parabricks.
"""

from stargazer.config import pb_env
from stargazer.types import Reference, Reads, Alignment
from stargazer.utils import _run


@pb_env.task
async def fq2bam(
    reads: Reads,
    ref: Reference,
    read_group: dict[str, str] | None = None,
) -> Alignment:
    """
    Align FASTQ reads to reference, sort, and mark duplicates.

    Uses Parabricks fq2bam (BWA-MEM + sorting + mark duplicates).

    Args:
        reads: Input FASTQ files (paired-end or single-end)
        ref: Reference genome with BWA index and FAI
        read_group: Optional read group override (ID, SM, LB, PL, PU)
                   If not provided, defaults to SM=sample_id

    Returns:
        Alignment object with sorted, duplicate-marked BAM

    Example:
        ref = await Reference.pinata_hydrate(ref_name="GRCh38.fa")
        ref = await samtools_faidx(ref)
        ref = await bwa_index(ref)
        reads = await Reads.pinata_hydrate(sample_id="NA12829")
        alignment = await fq2bam(reads=reads, ref=ref)

    Reference:
        https://docs.nvidia.com/clara/parabricks/latest/documentation/tooldocs/man_fq2bam.html
    """
    # Fetch all input files to cache
    await reads.fetch()
    await ref.fetch()

    # Get paths to input files
    ref_path = ref.get_ref_path()
    r1_path = reads.get_r1_path()
    r2_path = reads.get_r2_path()

    # Build read group string
    if read_group:
        rg_parts = [f"{k}:{v}" for k, v in read_group.items()]
        rg_string = "@RG\\t" + "\\t".join(rg_parts)
    else:
        # Default read group with sample ID
        rg_string = f"@RG\\tID:{reads.sample_id}\\tSM:{reads.sample_id}"

    # Create output BAM path in a temporary directory
    # We'll use the cache directory for temporary outputs
    output_dir = ref_path.parent
    output_bam = output_dir / f"{reads.sample_id}_aligned.bam"

    # Build fq2bam command
    cmd = [
        "pbrun",
        "fq2bam",
        "--ref",
        str(ref_path),
        "--out-bam",
        str(output_bam),
        "--bwa-options",
        "-K 10000000",  # For reproducible results
    ]

    # Add FASTQ inputs
    if r2_path:
        # Paired-end
        cmd.extend(["--in-fq", str(r1_path), str(r2_path), rg_string])
    else:
        # Single-end
        cmd.extend(["--in-se-fq", str(r1_path), rg_string])

    # Execute fq2bam
    stdout, stderr = await _run(cmd, cwd=str(output_dir))

    # Verify output BAM was created
    if not output_bam.exists():
        raise FileNotFoundError(
            f"fq2bam did not create output BAM at {output_bam}. stderr: {stderr}"
        )

    # Create Alignment object first, then add files to trigger upload
    alignment = Alignment(
        sample_id=reads.sample_id,
        bam_name=output_bam.name,
    )

    # Build metadata for BAM file
    keyvalues = {
        "type": "alignment",
        "sample_id": reads.sample_id,
        "tool": "fq2bam",
        "file_type": "bam",
        "sorted": "coordinate",
        "duplicates_marked": "true",  # fq2bam marks duplicates by default
    }

    # Upload BAM file to Pinata and add to alignment
    await alignment.add_files(file_paths=[output_bam], keyvalues=keyvalues)

    return alignment
