from typing import List
from flytekit import dynamic, task
from flytekit.extras.tasks.shell import subproc_execute
from flytekit.types.file import FlyteFile
from unionbio.config import logger
from unionbio.images import main_img
from unionbio.types import Alignment


@task(container_image=main_img)
def mark_dups(al: Alignment) -> Alignment:
    """
    Identify and remove duplicates from an alignment file using GATK's MarkDuplicates tool.

    This function takes in an alignment file, removes the duplicates and writes out
    a deduped alignment file.

    Args:
        al (Alignment): An alignment object.

    Returns:
        Alignment: An alignment object with the deduped alignment file and deduplication metrics.
    """
    logger.info(f"Marking duplicates for {al}")
    al.alignment.download()
    al.deduped = True
    mets = al.get_metrics_fname()
    al_out = al.get_alignment_fname()

    cmd = [
        "gatk",
        "MarkDuplicates",
        "-I",
        al.alignment.path,
        "-O",
        al_out,
        "-M",
        mets,
    ]
    logger.debug(f"Running command: {cmd}")
    subproc_execute(cmd)

    al.alignment = FlyteFile(path=al_out)
    al.dedup_metrics = FlyteFile(path=mets)
    logger.info(f"Returning: {al}")
    return al


@dynamic(container_image=main_img)
def mark_dups_samples(als: List[Alignment]) -> List[Alignment]:
    return [mark_dups(al=al) for al in als]
