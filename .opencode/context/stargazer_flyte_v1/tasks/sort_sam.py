from typing import List
from flytekit import dynamic, task
from flytekit.extras.tasks.shell import subproc_execute
from flytekit.types.file import FlyteFile
from unionbio.config import logger
from unionbio.images import main_img
from unionbio.types import Alignment


@task(container_image=main_img)
def sort_sam(al: Alignment) -> Alignment:
    """
    Sort an alignment file using GATK's SortSam tool.

    Args:
        al (Alignment): An alignment object.

    Returns:
        Alignment: An alignment object with the sorted alignment file.
    """
    logger.info(f"Sorting: {al}")
    al.alignment.download()
    al.sorted = True
    al_out = al.get_alignment_fname()

    cmd = [
        "gatk",
        "SortSam",
        "-I",
        al.alignment.path,
        "-O",
        al_out,
        "-SO",
        "coordinate",
    ]
    logger.debug(f"Running command: {cmd}")
    subproc_execute(cmd)

    al.alignment = FlyteFile(path=al_out)
    logger.info(f"Returning: {al}")
    return al


@dynamic(container_image=main_img)
def sort_samples(als: List[Alignment]) -> List[Alignment]:
    return [sort_sam(al=al) for al in als]
