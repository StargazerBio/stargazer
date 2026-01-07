from typing import List
from flytekit import workflow
from unionbio.tasks.bwa import bwa_index
from unionbio.tasks.parabricks import pb_fq2bam, pb_deepvar, pb_haplocall
from unionbio.types import VCF
from unionbio.tasks.utils import (
    fetch_remote_reads,
    fetch_remote_reference,
    fetch_remote_sites,
    intersect_vcfs,
)


@workflow
def wgs_small_var_calling_wf(
    reads: List[str] = [
        "https://storage.googleapis.com/brain-genomics-public/research/sequencing/fastq/hiseqx/wgs_pcr_free/30x/HG002.hiseqx.pcr-free.30x.R1.fastq.gz",
        "https://storage.googleapis.com/brain-genomics-public/research/sequencing/fastq/hiseqx/wgs_pcr_free/30x/HG002.hiseqx.pcr-free.30x.R2.fastq.gz",
    ],
    ref: str = "ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz",
    sites: List[str] = [
        "https://storage.googleapis.com/genomics-public-data/resources/broad/hg38/v0/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
        "https://storage.googleapis.com/genomics-public-data/resources/broad/hg38/v0/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz.tbi",
    ],
) -> VCF:
    read_obj = fetch_remote_reads(urls=reads)
    ref_obj = fetch_remote_reference(url=ref)
    sites_obj = fetch_remote_sites(sites=sites[0], idx=sites[1])
    ref_idx = bwa_index(ref_obj=ref_obj)
    alignment = pb_fq2bam(reads=read_obj, sites=sites_obj, ref=ref_idx)
    deepvar_vcf = pb_deepvar(al=alignment, ref=ref_idx)
    haplocall_vcf = pb_haplocall(al=alignment, ref=ref_idx)
    return intersect_vcfs(vcf1=deepvar_vcf, vcf2=haplocall_vcf)
