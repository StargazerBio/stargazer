import os
from pathlib import Path
from flytekit import task, dynamic, current_context
from flytekit.extras.tasks.shell import subproc_execute
from flytekit.types.file import FlyteFile
from unionbio.images import main_img
from unionbio.config import logger
from unionbio.types import Reference, Alignment, VCF


@task(container_image=main_img)
def base_recalibrator(ref: Reference, sites: VCF, al: Alignment) -> Alignment:
    """
    Recalibrate base quality scores using GATK's BaseRecalibrator.

    Args:
        ref (Reference): A reference object containing the reference FASTA file.
        sites (VCF): A VCF object containing known variant sites.
        al (Alignment): An alignment object containing the aligned reads.

    Returns:
        Alignment: An alignment object with the recalibrated alignment file.
    """
    ref.aggregate()
    sites.aggregate()
    al.aggregate()
    con_dir = Path(current_context().working_directory)
    logger.debug(
        f"Sites obj:\n{sites.sample}\n{sites.caller}\n{sites.vcf.path}\n{sites.vcf_idx.path}"
    )
    recal_fn = al.get_bqsr_fname()

    gen_table_cmd = [
        "gatk",
        "BaseRecalibrator",
        "-I",
        str(al.alignment.path),
        "-R",
        str(ref.get_ref_path()),
        "--known-sites",
        str(sites.vcf.path),
        "-O",
        str(recal_fn),
    ]
    logger.debug("Running GATK BaseRecalibrator with command:")
    logger.debug(" ".join(gen_table_cmd))
    logger.debug(f"Files present in context: {os.listdir(con_dir)}")
    subproc_execute(command=gen_table_cmd, cwd=con_dir)

    al.recalibrated = True
    al_out_fname = con_dir.joinpath(al.get_alignment_fname())
    apply_recal_cmd = [
        "gatk",
        "ApplyBQSR",
        "-I",
        al.alignment.path,
        "-R",
        ref.get_ref_path(),
        "--bqsr-recal-file",
        recal_fn,
        "-O",
        al_out_fname,
    ]
    subproc_execute(command=apply_recal_cmd, cwd=con_dir)

    al.alignment = FlyteFile(path=str(al_out_fname))

    return al


@dynamic(container_image=main_img)
def recalibrate_samples(
    als: list[Alignment], sites: VCF, ref: Reference
) -> list[Alignment]:
    return [base_recalibrator(ref=ref, sites=sites, al=al) for al in als]
