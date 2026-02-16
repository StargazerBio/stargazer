from datetime import timedelta
from typing import List
from flytekit import approve, conditional, dynamic, map_task, workflow
from flytekit.types.directory import FlyteDirectory
from flytekit.types.file import FlyteFile
from unionbio.config import ref_loc, seq_dir_pth
from unionbio.tasks.bowtie2 import bowtie2_align_paired_reads, bowtie2_index
from unionbio.tasks.fastp import pyfastp
from unionbio.tasks.fastqc import fastqc
from unionbio.tasks.hisat2 import hisat2_align_paired_reads, hisat2_index
from unionbio.tasks.multiqc import render_multiqc
from unionbio.tasks.sample_types import FiltSample, Alignment
from unionbio.tasks.utils import check_fastqc_reports, prepare_raw_samples


@dynamic
def compare_aligners(
    bt2_idx: FlyteDirectory, hs2_idx: FlyteDirectory, samples: List[FiltSample]
) -> List[Alignment]:
    """
    Compare alignment results using two different aligners for multiple samples.

    This function takes two FlyteDirectory objects representing indices for two different
    aligners, a list of FiltSample objects containing sample data, and compares the
    alignment results for each sample using both aligners. The function returns a
    list of lists, where each inner list contains the alignment results (SamFile objects)
    for a sample ran through each aligner.

    Args:
        bt2_idx (FlyteDirectory): The FlyteDirectory object representing the bowtie2 index.
        hs2_idx (FlyteDirectory): The FlyteDirectory object representing the hisat2 index.
        samples (List[FiltSample]): A list of FiltSample objects containing sample data
            to be processed.

    Returns:
        List[SamFile]: A list of alignment results (SamFile objects) for a sample,
        with results from both aligners.
    """
    sams = []
    for sample in samples:
        bt2_sam = bowtie2_align_paired_reads(idx=bt2_idx, fs=sample)
        hs2_sam = hisat2_align_paired_reads(idx=hs2_idx, fs=sample)
        sams.append(bt2_sam)
        sams.append(hs2_sam)
    return sams


@workflow
def alignment_wf(seq_dir: FlyteDirectory = seq_dir_pth) -> FlyteFile:
    """
    Run an alignment workflow on FastQ files contained in the configured seq_dir.

    This function performs QC, preprocessing, index generation, and finally aligments
    on FastQ input files present in a preconfigured S3 prefix. It returns a FlyteFile
    of a MultiQC report containing all relevant statistics of the different steps.

    Args:
        seq_dir (FlyteDirectory, optional): The input directory containing sequencing data.
            Defaults to the value of `seq_dir` (if provided).

    Returns:
        FlyteFile: A FlyteFile object representing the output of the alignment workflow.
    """
    # Generate FastQC reports and check for failures
    fqc_dir = fastqc(seq_dir=seq_dir)
    check = check_fastqc_reports(rep_dir=fqc_dir)

    # If the FastQC summary is PASS or WARN then we can proceed with the workflow.
    # If there is at least one FAIL, then the workflow fails.
    samples = (
        conditional("pass-qc")
        .if_((check == "PASS") | (check == "WARN"))
        .then(prepare_raw_samples(seq_dir=seq_dir))
        .else_()
        .fail("One or more samples failed QC.")
    )

    # Map out filtering across all samples and generate indices
    filtered_samples = map_task(pyfastp)(rs=samples)
    approve_filter = approve(
        render_multiqc(fqc=fqc_dir, filt_reps=filtered_samples, sams=[]),
        "filter-approval",
        timeout=timedelta(hours=2),
    )

    bowtie2_idx = bowtie2_index(ref=ref_loc)
    hisat2_idx = hisat2_index(ref=ref_loc)

    # Require that samples pass QC before potentially expensive index generation
    samples >> approve_filter >> bowtie2_idx
    samples >> approve_filter >> hisat2_idx

    # Compare alignment results using two different aligners in a dynamic task
    sams = compare_aligners(
        bt2_idx=bowtie2_idx, hs2_idx=hisat2_idx, samples=filtered_samples
    )

    # Generate final multiqc report with stats from all steps
    return render_multiqc(fqc=fqc_dir, filt_reps=filtered_samples, sams=sams)
