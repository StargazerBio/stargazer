from flytekit import workflow
from flytekit.types.directory import FlyteDirectory
from flytekit.types.file import FlyteFile
from flytekit import map_task
from unionbio.config import ref_loc, seq_dir_pth
from unionbio.tasks.fastqc import fastqc
from unionbio.tasks.fastp import pyfastp
from unionbio.tasks.utils import prepare_raw_samples
from unionbio.tasks.bowtie2 import bowtie2_align_samples, bowtie2_index
from unionbio.tasks.multiqc import render_multiqc


@workflow
def simple_alignment_wf(seq_dir: FlyteDirectory = seq_dir_pth) -> FlyteFile:
    """
    Run an alignment workflow on FastQ files contained in the configured seq_dir.

    This function performs QC, preprocessing, index generation, and finally alignments
    on FastQ input files present in a pre-configured S3 prefix. It returns a FlyteFile
    of a MultiQC report containing all relevant statistics of the different steps.

    Args:
        seq_dir (FlyteDirectory, optional): The input directory containing sequencing data.
            Defaults to the value of `seq_dir` (if provided).

    Returns:
        FlyteFile: A FlyteFile object representing the output of the alignment workflow.
    """
    # Generate FastQC reports and check for failures
    fqc_out = fastqc(seq_dir=seq_dir)
    samples = prepare_raw_samples(seq_dir=seq_dir)

    # Map out filtering across all samples and generate indices
    filtered_samples = map_task(pyfastp)(rs=samples)

    fqc_out >> filtered_samples

    bowtie2_idx = bowtie2_index(ref=ref_loc)

    # Compare alignment results using two different aligners in a dynamic task
    sams = bowtie2_align_samples(idx=bowtie2_idx, samples=filtered_samples)

    # Generate final multiqc report with stats from all steps
    return render_multiqc(fqc=fqc_out, filt_reps=filtered_samples, sams=sams)
