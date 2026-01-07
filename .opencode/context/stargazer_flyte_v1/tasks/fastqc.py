from pathlib import Path
from typing import List
from flytekit import task, current_context
from flytekit.extras.tasks.shell import subproc_execute
from flytekit.types.directory import FlyteDirectory
from unionbio.config import logger
from unionbio.images import main_img
from unionbio.types import Reads


@task(container_image=main_img)
def fastqc(reads: List[Reads]) -> FlyteDirectory:
    """
    Perform quality control using FastQC.

    This function takes a FlyteDirectory object containing raw sequencing data,
    gathers QC metrics using FastQC, and returns a FlyteDirectory object that
    can be crawled with MultiQC to generate a report.

    Args:
        reads (List[Reads]): A list of Reads objects containing raw sequencing data.

    Returns:
        qc (FlyteDirectory): A directory containing fastqc report output.
    """
    pwd = Path(current_context().working_directory)
    indir = pwd.joinpath("fastqc_in")
    outdir = pwd.joinpath("fastqc_out")
    outdir.mkdir()
    for r in reads:
        r.aggregate(target=indir)
    logger.debug(f"Aggregated reads to {indir} with contents: {list(indir.iterdir())}")
    fqc_cmd = [
        "fastqc",
        f"{indir}/*.fastq*",
        "--outdir",
        str(outdir),
    ]
    fqc_cmd_str = " ".join(fqc_cmd)
    logger.debug("Running FastQC with command:")
    logger.debug(fqc_cmd_str)
    res = subproc_execute(fqc_cmd_str, shell=True)
    logger.debug(f"FastQC command returned: {res}")
    logger.debug(
        f"FastQC reports generated at {outdir} with contents: {list(outdir.iterdir())}"
    )

    return FlyteDirectory(path=outdir)
