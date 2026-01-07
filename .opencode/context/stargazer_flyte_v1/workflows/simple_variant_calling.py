from flytekit import workflow
from flytekit import map_task
from typing import List
from unionbio.config import (
    remote_reads,
    remote_ref,
    remote_sites_vcf,
    remote_sites_idx,
)
from unionbio.tasks.fastqc import fastqc
from unionbio.tasks.fastp import pyfastp
from unionbio.tasks.utils import (
    reformat_alignments,
    fetch_remote_reads,
    fetch_remote_reference,
    fetch_remote_sites,
)
from unionbio.tasks.bwa import bwa_align_samples, bwa_index
from unionbio.tasks.multiqc import render_multiqc
from unionbio.tasks.base_recal import recalibrate_samples
from unionbio.tasks.mark_dups import mark_dups_samples
from unionbio.tasks.sort_sam import sort_samples
from unionbio.tasks.haplotype_caller import hc_call_samples
from unionbio.types import VCF


@workflow
def calling_wf(
    ref_url: str = remote_ref,
    reads_urls: List[str] = remote_reads,
    remote_sites_vcf: str = remote_sites_vcf,
    remote_sites_idx: str = remote_sites_idx,
) -> List[VCF]:
    """
    Run an alignment and variant calling workflow on FastQ files.

    This function performs QC, preprocessing, index generation, alignment, and variant calling
    on FastQ input files present in a pre-configured remote URL. It returns a list of VCF objects
    containing the variant calls for each sample.

    Args:
        ref_url (str): The URL of the reference genome to use for alignment.
        reads_urls (List[str]): A list of URLs pointing to the FastQ files to align.
        remote_sites_vcf (str): The URL of the VCF file containing known variant sites.
        remote_sites_idx (str): The URL of the tabix index for the VCF file.

    Returns:
        List[VCF]: A list of VCF objects containing the variant calls for each sample.
    """
    # Fetch remote inputs
    ref = fetch_remote_reference(url=ref_url)
    reads = fetch_remote_reads(urls=reads_urls)
    sites = fetch_remote_sites(sites=remote_sites_vcf, idx=remote_sites_idx)

    # Generate FastQC reports and check for failures
    fqc_out = fastqc(reads=reads)

    # Map out filtering across all samples and generate indices
    filtered_samples = map_task(pyfastp)(rs=reads)

    # Explicitly define task dependencies
    fqc_out >> filtered_samples

    # Generate final multiqc report with preprocessing steps
    render_multiqc(fqc=fqc_out, filt_reps=filtered_samples)

    # Generate a bowtie2 index or load it from cache
    idx = bwa_index(ref=ref)

    # Generate alignments using bowtie2
    sams = bwa_align_samples(idx=idx, samples=filtered_samples)

    # Recalibrate & Reformat
    sorted = sort_samples(als=sams)
    deduped = mark_dups_samples(als=sorted)
    recal_sams = recalibrate_samples(als=deduped, sites=sites, ref=idx)
    bams = reformat_alignments(als=recal_sams, to_format="bam")

    # Call Variants
    vcfs = hc_call_samples(ref=idx, als=bams)

    return vcfs
