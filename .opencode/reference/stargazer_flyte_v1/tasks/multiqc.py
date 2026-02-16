import os
import shutil
from flytekit import current_context, task
from flytekit.types.directory import FlyteDirectory
from flytekit.types.file import FlyteFile
from flytekit.extras.tasks.shell import subproc_execute
from typing import List
from pathlib import Path
from unionbio.config import logger
from unionbio.images import main_img
from unionbio.types import Alignment, Reads, VCF


@task(container_image=main_img, enable_deck=True)
def render_multiqc(
    fqc: FlyteDirectory,
    filt_reps: List[Reads] | None,
    sams: List[Alignment] | None,
    vcfs: List[VCF] | None,
) -> FlyteFile:
    """
    Generate MultiQC report by rendering quality and alignment data.

    Takes a FlyteDirectory object containing FastQC reports (`fqc`),
    a list of FiltSample objects containing reports (`filt_reps`), and a
    list of lists of SamFile objects representing alignment results (`sams`). It generates
    a MultiQC report by rendering quality and alignment data and returns a FlyteFile object
    of the report.

    Args:
        fqc (FlyteDirectory): A FlyteDirectory object containing FastQC reports.
        filt_reps (List[FiltSample]): A list of FiltSample objects representing filtered samples.
        sams (List[List[SamFile]]): A list of lists of SamFile objects representing alignment results.
        vcfs (List[VCF]): An optional list of VCF objects containing calling stats.

    Returns:
        FlyteFile: A FlyteFile object representing the MultiQC report.
    """
    ldir = Path(current_context().working_directory)

    fqc.download()
    for f in os.listdir(fqc.path):
        src = ldir.joinpath(fqc.path, f)
        dest = ldir.joinpath(ldir, f)
        shutil.move(src, dest)
    logger.debug(f"FastQC reports downloaded to {ldir}")

    if filt_reps:
        for filt_rep in filt_reps:
            filt_rep.filt_report.download()
            shutil.move(filt_rep.filt_report.path, ldir)
        logger.debug(f"FastP reports downloaded to {ldir}")

    if sams:
        for sam in sams:
            sam.alignment_report.download()
            shutil.move(sam.alignment_report.path, ldir)
        logger.debug(f"Alignment reports for {sams} downloaded to {ldir}")

    final_report = ldir.joinpath("multiqc_report.html")
    mqc_cmd = ["multiqc", str(ldir), "-n", str(final_report)]
    logger.debug(f"Generating MultiQC report at {final_report} with command: {mqc_cmd}")
    subproc_execute(mqc_cmd)

    # Hack to force render plots on page load
    report_html_lst = []
    hack = """
  // Force render plots on page load
  $(".hc-plot").each(function () {
    var target = $(this).attr("id");
    var max_num = mqc_config["num_datasets_plot_limit"] * 50;
    plot_graph(target, undefined, max_num);
  });
  """
    with open(final_report, "r") as f:
        for line in f:
            if "// Render plots on page load" in line:
                report_html_lst.append(hack)
                report_html_lst.append(line)
            else:
                report_html_lst.append(line)
    report_html = "".join(report_html_lst)

    current_context().default_deck.append(report_html)
    logger.debug("MultiQC report HTML added to default deck")

    return FlyteFile(path=str(final_report))
