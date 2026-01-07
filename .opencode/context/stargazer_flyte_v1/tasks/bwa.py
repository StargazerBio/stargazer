import os
from pathlib import Path
from typing import List
from flytekit import task, Resources, current_context, dynamic
from flytekit.extras.tasks.shell import subproc_execute
from flytekit.types.file import FlyteFile
from flytekit.types.directory import FlyteDirectory
from unionbio.config import remote_ref, logger
from unionbio.images import main_img
from unionbio.types import Reference, Reads, Alignment


@task(
    container_image=main_img,
    requests=Resources(cpu="4", mem="10Gi"),
    cache=True,
    cache_version=remote_ref,
)
def bwa_index(ref: Reference) -> Reference:
    """Indexes a reference genome using BWA.

    Args:
        ref (Reference): The reference object containing the reference genome.

    Returns:
        Reference: The updated reference object with associated index and metadata.
    """
    ref.aggregate()

    if f"{ref.ref_name}.fai" not in os.listdir(ref.ref_dir.path):
        sam_idx = ["samtools", "faidx", str(ref.get_ref_path())]
        subproc_execute(sam_idx, cwd=ref.ref_dir.path)
    ref_dict = Path(ref.ref_dir.path).joinpath(ref.get_ref_dict_fn())
    if ref_dict not in os.listdir(ref.ref_dir.path):
        logger.debug(f"Generating sequence dictionary {ref_dict} for {ref.ref_name}")
        subproc_execute(
            ["samtools", "dict", ref.ref_name, "-o", ref_dict], cwd=ref.ref_dir.path
        )
        logger.debug(f"Reference dict exists: {ref_dict.exists()}")
    bwa_idx = ["bwa", "index", str(ref.get_ref_path())]
    subproc_execute(bwa_idx, cwd=ref.ref_dir.path)
    logger.debug(f"Indexing complete for {ref.ref_name}")
    logger.debug(f"Reference dir contents: {os.listdir(ref.ref_dir.path)}")
    ref.index_name = ref.ref_name
    ref.indexed_with = "bwa"
    ref.ref_dir = FlyteDirectory(path=ref.ref_dir.path)

    return ref


@task(
    container_image=main_img,
    requests=Resources(cpu="4", mem="10Gi"),
)
def bwa_align(ref: Reference, reads: Reads, rgtag: str = "") -> Alignment:
    """Aligns reads to a reference genome using BWA.

    Args:
        ref (Reference): The reference object containing the reference genome and index.
        reads (Reads): The reads object containing the reads to align.
        rgtag (str): The read group tag to include in the alignment header.

    Returns:
        Alignment: The alignment object containing the aligned reads.
    """
    ref.aggregate()
    reads.aggregate()
    if rgtag:
        rgtag = repr(f"{rgtag}")
    else:
        rgtag = repr("@RG\tID:default\tSM:sample\tPL:illumina\tLB:lib1\tPU:unit1")
    al_out = Alignment(
        sample=reads.sample,
        aligner="bwa",
        format="sam",
        sorted=False,
        deduped=False,
    )
    con_dir = current_context().working_directory
    sam_out = Path(con_dir).joinpath(al_out.get_alignment_fname())
    bwa_align = [
        "bwa",
        "mem",
        "-R",
        rgtag,
        str(ref.get_ref_path()),
        str(reads.read1.path),
        str(reads.read2.path),
        ">",
        str(sam_out),
    ]
    cmd_str = " ".join(bwa_align)
    logger.info(f"Running BWA alignment with: {cmd_str}")
    logger.debug(f"Running in {con_dir} with contents: {os.listdir(con_dir)}")
    subproc_execute(cmd_str, shell=True, cwd=con_dir)
    sp = Path(sam_out)
    logger.debug(f"Alignment exists ({sp.exists()}) at {sp.resolve()}")
    al_out.alignment = FlyteFile(path=str(sam_out))
    return al_out


@dynamic(container_image=main_img)
def bwa_align_samples(idx: Reference, samples: List[Reads]) -> List[Alignment]:
    """
    Process samples through BWA.

    This function takes a Reference object containing a bwa index and a list of
    Reads objects containing filtered sample data. It performs paired-end alignment
    using bwa. It then returns a list of Alignment objects representing the alignment results.

    Args:
        idx (Reference): The Reference object containing the bowtie2 index.
        samples (List[Reads]): A list of Reads objects containing sample data
            to be processed.

    Returns:
        [List[Alignment]: A list of alignment results (Alignment objects).
    """
    return [bwa_align(ref=idx, reads=sample) for sample in samples]
