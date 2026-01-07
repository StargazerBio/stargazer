import os
from pathlib import Path
from typing import List
from flytekit import task, Resources, dynamic
from flytekit.extras.tasks.shell import subproc_execute
from flytekit.types.file import FlyteFile
from flytekit.types.directory import FlyteDirectory
from unionbio.images import main_img
from unionbio.config import logger
from unionbio.types import Alignment, Reads, Reference


@task(
    container_image=main_img,
    requests=Resources(cpu="4", mem="10Gi"),
)
def bowtie2_index(ref: Reference) -> Reference:
    """
    Generate a Bowtie 2 index for a reference genome.

    Args:
        ref (Reference): A Reference object containing the reference genome to be indexed.

    Returns:
        Reference: A Reference object with the Bowtie 2 index added in.
    """
    ref.aggregate()
    if f"{ref.ref_name}.fai" not in os.listdir(ref.ref_dir.path):
        logger.debug(f"Samtools indexing {ref.ref_name}")
        subproc_execute(["samtools", "faidx", ref.ref_name], cwd=ref.ref_dir.path)
    ref_dict = ref.get_ref_dict_fn()
    if ref_dict not in os.listdir(ref.ref_dir.path):
        logger.debug(f"Generating sequence dictionary {ref_dict} for {ref.ref_name}")
        subproc_execute(
            ["samtools", "dict", ref.ref_name, "-o", ref_dict], cwd=ref.ref_dir.path
        )
        logger.debug(f"Reference dict exists: {ref_dict.exists()}")
    ref.index_name = "bt2_idx"
    ref.indexed_with = "bowtie2"
    idx_cmd = ["bowtie2-build", ref.ref_name, ref.index_name]
    logger.debug(f"Running command: {idx_cmd}")
    subproc_execute(idx_cmd, cwd=ref.ref_dir.path)
    logger.debug(
        f"Index created at {ref.ref_dir.path} with contents {os.listdir(ref.ref_dir.path)}"
    )
    ref.ref_dir = FlyteDirectory(path=ref.ref_dir.path)
    return ref


@task(
    container_image=main_img,
    requests=Resources(cpu="4", mem="10Gi"),
)
def bowtie2_align_paired_reads(idx: Reference, fs: Reads) -> Alignment:
    """
    Perform paired-end alignment using Bowtie 2 on a filtered sample.

    This function takes a Reference object containing the Bowtie 2 index and a
    FiltSample object containing filtered sample data. It performs paired-end alignment
    using Bowtie 2 and returns a Alignment object representing the resulting alignment.

    Args:
        idx (Reference): A Reference object containing the Bowtie 2 index.
        fs (Reads): A filtered sample Reads object containing filtered sample data to be aligned.

    Returns:
        Alignment: An Alignment object representing the alignment result.
    """
    idx.aggregate()
    fs.aggregate()
    logger.debug(f"Index downloaded to {idx.ref_dir.path}")
    alignment = Alignment(fs.sample, "bowtie2", "sam", sorted=False, deduped=False)
    al = Path(alignment.get_alignment_fname()).resolve()
    rep = Path(alignment.get_report_fname()).resolve()
    logger.debug(f"Writing alignment to {al} and report to {rep}")

    cmd = [
        "bowtie2",
        "-x",
        idx.index_name,
        "-1",
        str(fs.read1.path),
        "-2",
        str(fs.read2.path),
        "-S",
        str(al),
    ]

    logger.debug(f"Running command: {cmd}")
    result = subproc_execute(cmd, cwd=idx.ref_dir.path)
    logger.debug(f"Alignment produced: {al.exists()}")
    with open(rep, "w") as f:
        f.write(result.error)

    alignment.alignment = FlyteFile(path=str(al))
    alignment.alignment_report = FlyteFile(path=str(rep))
    return alignment


@dynamic(container_image=main_img)
def bowtie2_align_samples(idx: Reference, samples: List[Reads]) -> List[Alignment]:
    """
    Process samples through bowtie2.

    This function takes a FlyteDirectory objects representing a bowtie index and a list of
    Reads objects containing filtered sample data. It performs paired-end alignment
    using bowtie2. It then returns a list of Alignment objects representing the alignment results.

    Args:
        bt2_idx (FlyteDirectory): The FlyteDirectory object representing the bowtie2 index.
        samples (List[Reads]): A list of Reads objects containing sample data
            to be processed.

    Returns:
        List[List[Alignment]]: A list of lists, where each inner list contains alignment
            results (Alignment objects) for a sample, with results from both aligners.
    """
    sams = []
    for sample in samples:
        sam = bowtie2_align_paired_reads(idx=idx, fs=sample)
        sams.append(sam)
    return sams
