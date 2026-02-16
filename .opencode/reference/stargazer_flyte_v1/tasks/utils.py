import os
import zipfile
import requests
import tarfile
from time import time
from pathlib import Path
from flytekit import task, current_context
from flytekit.types.directory import FlyteDirectory
from flytekit.types.file import FlyteFile
from flytekit.extras.tasks.shell import subproc_execute
from unionbio.config import logger
from unionbio.images import main_img  # , parabricks_img
from unionbio.tasks.helpers import fetch_file
from unionbio.types import Reads, Reference, VCF, Alignment, Protein


@task(container_image=main_img)
def prepare_raw_samples(seq_dir: FlyteDirectory) -> list[Reads]:
    """
    Prepare and process raw sequencing data to create a list of RawSample objects.

    This function processes raw sequencing data located in the specified input directory
    and prepares it to create a list of RawSample objects.

    Args:
        seq_dir (FlyteDirectory): The input directory containing raw sequencing data.

    Returns:
        list[Reads]: A list of Reads objects representing the processed sequencing data.
    """
    seq_dir.download()
    return Reads.make_all(Path(seq_dir))


@task(container_image=main_img)
def fetch_remote_reference(url: str) -> Reference:
    workdir = current_context().working_directory
    ref_path = fetch_file(url, workdir)
    return Reference(ref_name=str(ref_path.name), ref_dir=FlyteDirectory(path=workdir))


@task(container_image=main_img)
def fetch_remote_reads(urls: list[str]) -> list[Reads]:
    """
    Fetches remote reads from a list of URLs and returns a list of Reads objects.

    Args:
        urls (list[str]): A list of URLs pointing to the reads to fetch.

    Returns:
        list[Reads]: A list of Reads objects representing the fetched reads.
    """
    workdir = current_context().working_directory
    for url in urls:
        fetch_file(url, workdir)
    return Reads.make_all(Path(workdir))


@task(container_image=main_img)
def fetch_remote_sites(sites: str, idx: str) -> VCF:
    """
    Fetches remote known sites from a URL and returns a Sites object.

    Args:
        sites (str): The URL of the known sites VCF file.
        idx (str): The URL of the known sites VCF index file

    Returns:
        VCF: A VCF object representing the fetched known sites.
    """
    workdir = current_context().working_directory
    sites_path = fetch_file(sites, workdir)
    idx_path = fetch_file(idx, workdir)
    sample_name = Path(sites_path.stem)
    while sample_name.suffix:
        sample_name = sample_name.with_suffix("")
    return VCF(
        sample=str(sample_name),
        caller="NA",
        vcf=FlyteFile(path=str(sites_path)),
        vcf_idx=FlyteFile(path=str(idx_path)),
    )


@task(container_image=main_img)
def fetch_remote_protein(urls: list[str]) -> Protein:
    """
    Fetches files from a list of URLs and returns a list of Protein objects.

    Args:
        urls (list[str]): A list of URLs pointing to a3m, h8, fasta etc files.

    Returns:
        Protein: A Protein object representing the fetched files.
    """
    workdir = current_context().working_directory
    for url in urls:
        logger.debug(f"Fetching {url}")
        fetch_file(url, workdir)
    prots = Protein.make_all(Path(workdir))
    if len(prots) > 1:
        logger.warning(
            f"More than 1 Protein object created from provided URLs: {prots}. Returning index 0."
        )
    return prots[0]


@task
def fetch_files(urls: list[str]) -> list[FlyteFile]:
    """
    Fetches files from a list of URLs and returns a list of FlyteFile objects.

    Args:
        urls (list[str]): A list of URLs pointing to the files to fetch.

    Returns:
        list[FlyteFile]: A list of FlyteFile objects representing the fetched files.
    """
    outfiles = []
    workdir = current_context().working_directory
    for url in urls:
        lpath = fetch_file(url, workdir)
        outfiles.append(FlyteFile(path=lpath))
    return outfiles


@task
def fetch_tarfile(url: str) -> FlyteDirectory:
    """
    Downloads a tar.gz file from the specified URL, extracts its contents, and returns a FlyteDirectory object.

    Args:
        url (str): The URL of the tar.gz file to download.

    Returns:
        FlyteDirectory: A FlyteDirectory object representing the directory where the contents of the tar.gz file were extracted.

    Raises:
        requests.HTTPError: If an HTTP error occurs while downloading the file.
    """
    try:
        response = requests.get(url)
        tar_name = url.split("/")[-1]
        with open(tar_name, "wb") as file:
            file.write(response.content)
    except requests.HTTPError as e:
        print(f"HTTP error: {e}")
        raise e

    working_dir = current_context().working_directory
    out_dir = Path(os.path.join(working_dir, tar_name))
    with tarfile.open(tar_name, "r:gz") as tarf:
        tarf.extractall(out_dir)

    return FlyteDirectory(path=out_dir)


@task
def check_fastqc_reports(rep_dir: FlyteDirectory) -> str:
    """
    Check FastQC reports for errors.

    This function checks FastQC reports for errors and raises an exception if any are found.

    Args:
        rep_dir (FlyteDirectory): The input directory containing FastQC reports.

    Returns:
        str: The status of the FastQC reports (PASS, WARN, or FAIL).
    """
    rep_dir.download()
    all_zips = list(Path(rep_dir.path).rglob("*fastqc.zip*"))

    for p in all_zips:
        logger.debug(f"Checking {p}")
        with zipfile.ZipFile(p, "r") as zip_file:
            logger.debug(f"{zip_file.filename}")
            logger.debug(f"Archive contains {zip_file.namelist()}")
            with zip_file.open(
                f"{Path(zip_file.filename).stem}/summary.txt"
            ) as summary:
                contents = summary.read().decode("utf-8")
                logger.debug(f"Contents of summary.txt: {contents}")
                if "FAIL" in contents:
                    return "FAIL"
                elif "WARN" in contents:
                    return "WARN"

    return "PASS"


# @task(container_image=parabricks_img)
# def compare_bams(in1: FlyteFile, in2: FlyteFile) -> bool:
#     """
#     Compares two BAM files and returns True if they are identical, False otherwise.

#     Args:
#         in1 (FlyteFile): The first input BAM file.
#         in2 (FlyteFile): The second input BAM file.

#     Returns:
#         bool: True if the BAM files are identical, False otherwise.
#     """
#     in1.download()
#     in2.download()

#     cmp1 = [
#         "bam",
#         "diff",
#         "--in1",
#         in1.path,
#         "--in2",
#         in2.path,
#         "--noCigar",
#         "--isize",
#         "--flag",
#         "--mate",
#         "--mapQual",
#     ]

#     result = subproc_execute(cmp1)

#     no_out = result.out == "" and result.err == ""

#     return no_out


@task(
    container_image=main_img,
)
def intersect_vcfs(vcf1: VCF, vcf2: VCF) -> VCF:
    """
    Takes the intersection of 2 VCF files and returns a new VCF file to increase
    calling sensitivity.

    Args:
        vcf1 (VCF): The first input VCF object.
        vcf2 (VCF): The second input VCF object.

    Returns:
        VCF: Intersected and zipped VCF object.
    """
    vcf1.aggregate()
    vcf2.aggregate()
    isec_out = VCF(sample=vcf1.sample, caller=f"{vcf1.caller}_{vcf2.caller}_isec")
    fname_out = isec_out.get_vcf_fname()

    cmd = " ".join(
        [
            "bcftools",
            "isec",
            "-n=2",
            "-O",
            "z",
            "-w",
            "1",
            str(vcf1.vcf.path),
            str(vcf2.vcf.path),
            "-o",
            fname_out,
        ]
    )

    subproc_execute(cmd, shell=True)
    isec_out.vcf = FlyteFile(path=fname_out)

    return isec_out


@task(container_image=main_img)  # TODO: generalize
def reformat_alignments(als: list[Alignment], to_format: str) -> list[Alignment]:
    """
    Reformat alignment files to ensure they are in the correct format.

    Args:
        als (list[Alignment]): A list of Alignment objects containing the aligned reads.

    Returns:
        list[Alignment]: A list of Alignment objects with the reformatted alignment files.
    """
    als_out = []
    for al in als:
        al.aggregate()
        if to_format == "bam":
            al.format = "bam"
            al_out_fname = al.get_alignment_fname()
            convert_cmd = [
                "samtools",
                "view",
                "-S",
                "-b",
                str(al.alignment.path),
                "-o",
                al_out_fname,
            ]
            subproc_execute(convert_cmd)
            logger.debug("Running reformat cmd:")
            logger.debug(" ".join(convert_cmd))
            al.alignment = FlyteFile(path=al_out_fname)
            logger.debug(
                f"Reformatted alignment file {al_out_fname} exists: {os.path.exists(al_out_fname)}"
            )

            idx_fn = al.get_alignment_idx_fname()
            idx_cmd = ["samtools", "index", al_out_fname, "-o", idx_fn]
            logger.debug("Running index cmd:")
            logger.debug(" ".join(idx_cmd))
            subproc_execute(idx_cmd)
            logger.debug(f"Index file {idx_fn} exists: {os.path.exists(idx_fn)}")
            al.alignment_idx = FlyteFile(path=idx_fn)
        als_out.append(al)

    return als_out


@task
def s3_sync(
    db_uri: str,
    output_loc: str,
) -> str:
    os.makedirs(output_loc, exist_ok=True)

    dl_cmd = ["aws", "s3", "sync", db_uri, output_loc]

    cmd_str = " ".join(dl_cmd)
    logger.info(f"Downloading databases with command: {cmd_str}")
    start = time.time()

    subproc_execute(command=cmd_str, shell=True)

    elapsed = time.time() - start
    logger.info(f"Downloaded in {elapsed} seconds ({elapsed / 3600} hours)")
    logger.debug(f"Database files: {os.listdir(output_loc)}")
    return output_loc
