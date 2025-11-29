"""
Flyte tasks for NVIDIA Parabricks genomics tools.

This module provides Flyte task wrappers for Parabricks tools:
- fq2bam: Convert FASTQ files to BAM/CRAM with alignment and duplicate marking
- deepvariant: GPU-accelerated variant calling from BAM to VCF
- haplotypecaller: GPU-accelerated GATK HaplotypeCaller for variant calling
"""

import asyncio
from pathlib import Path
from typing import Optional, List
from stargazer.config import parabricks_env

import flyte
from flyte.io import File

from stargazer.types.parabricks import (
    Fq2BamOutputs,
    DeepVariantOutputs,
    HaplotypeCallerOutputs,
)


async def pbrun(
    tool: str,
    args: List[str],
    working_dir: Optional[Path] = None,
) -> tuple[int, str, str]:
    """
    Generic wrapper function to execute pbrun commands.

    Args:
        tool: The Parabricks tool to run (e.g., 'fq2bam', 'deepvariant', 'haplotypecaller')
        args: List of command-line arguments to pass to the tool
        working_dir: Optional working directory for the command

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd = ["pbrun", tool] + args

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=working_dir,
    )

    stdout, stderr = await process.communicate()

    return (
        process.returncode,
        stdout.decode("utf-8") if stdout else "",
        stderr.decode("utf-8") if stderr else "",
    )


@parabricks_env.task
async def fq2bam(
    ref: File,
    in_fq_r1: File,
    in_fq_r2: Optional[File] = None,
    known_sites: Optional[List[File]] = None,
    interval_file: Optional[File] = None,
    read_group_sm: Optional[str] = None,
    read_group_lb: Optional[str] = None,
    read_group_pl: Optional[str] = None,
    read_group_id_prefix: Optional[str] = None,
    out_bam_path: str = "output.bam",
    out_recal_path: Optional[str] = None,
    out_dup_metrics_path: Optional[str] = None,
    bwa_options: Optional[str] = None,
    no_markdups: bool = False,
    num_gpus: int = 1,
    gpusort: bool = True,
    gpuwrite: bool = True,
    gpuwrite_deflate_algo: Optional[int] = None,
    bwa_nstreams: str = "auto",
    low_memory: bool = False,
) -> Fq2BamOutputs:
    """
    Run Parabricks fq2bam: GPU-accelerated BWA-MEM alignment + sorting + duplicate marking.

    Converts FASTQ files to coordinate-sorted, duplicate-marked BAM/CRAM with optional BQSR.
    Combines BWA-MEM alignment, GATK SortSam, MarkDuplicates, and BaseRecalibrator in one tool.

    Args:
        ref: Reference genome FASTA file (must be BWA-indexed)
        in_fq_r1: First/forward FASTQ file (R1) - required
        in_fq_r2: Second/reverse FASTQ file (R2) for paired-end (None for single-end)
        known_sites: List of known variants VCF.gz files for BQSR (e.g., dbSNP, Mills indels)
        interval_file: Interval file (BED/Picard/GATK) for BQSR region selection
        read_group_sm: Sample name (SM) tag for read groups
        read_group_lb: Library (LB) tag for read groups
        read_group_pl: Platform (PL) tag for read groups (e.g., "ILLUMINA", "PACBIO")
        read_group_id_prefix: Prefix for read group ID and PU tags
        out_bam_path: Output BAM/CRAM file path (default: "output.bam")
        out_recal_path: BQSR recalibration report output path
        out_dup_metrics_path: Duplicate metrics file output path
        bwa_options: BWA-MEM options as string (e.g., "-M -Y -K 10000000")
        no_markdups: Skip duplicate marking, return sorted BAM only
        num_gpus: Number of GPUs to use (default: 1)
        gpusort: Use GPU-accelerated sorting (default: True)
        gpuwrite: Use GPU-accelerated BAM/CRAM compression (default: True)
        gpuwrite_deflate_algo: DEFLATE algorithm for --gpuwrite (1=fastest, 2/4=higher compression)
        bwa_nstreams: Streams per GPU ("auto" or integer, default: "auto")
        low_memory: Use low memory mode (reduces streams per GPU)

    Returns:
        Fq2BamOutputs with output BAM and optional recalibration report and duplicate metrics

    Notes:
        - BQSR runs only if both known_sites and out_recal_path are provided
        - For paired-end: provide both in_fq_r1 and in_fq_r2
        - For single-end: provide only in_fq_r1, set in_fq_r2=None
        - Read group tags are optional; auto-generated if not provided
        - Set bwa_options="-K 10000000" for BWA-MEM compatible output
    """
    # Download input files
    ref_local = await ref.download()
    fq1_local = await in_fq_r1.download()

    # Build command arguments
    args = [
        "--ref", ref_local,
        "--out-bam", out_bam_path,
        "--num-gpus", str(num_gpus),
    ]

    # Add FASTQ inputs (paired-end or single-end)
    if in_fq_r2:
        fq2_local = await in_fq_r2.download()
        args.extend(["--in-fq", fq1_local, fq2_local])
    else:
        args.extend(["--in-se-fq", fq1_local])

    # Add read group tags
    if read_group_sm:
        args.extend(["--read-group-sm", read_group_sm])
    if read_group_lb:
        args.extend(["--read-group-lb", read_group_lb])
    if read_group_pl:
        args.extend(["--read-group-pl", read_group_pl])
    if read_group_id_prefix:
        args.extend(["--read-group-id-prefix", read_group_id_prefix])

    # Add known sites for BQSR if provided
    if known_sites and out_recal_path:
        for ks_file in known_sites:
            ks_local = await ks_file.download()
            args.extend(["--knownSites", ks_local])
        args.extend(["--out-recal-file", out_recal_path])

    # Add interval file for BQSR
    if interval_file:
        interval_local = await interval_file.download()
        args.extend(["--interval-file", interval_local])

    # Add duplicate metrics output if requested
    if out_dup_metrics_path:
        args.extend(["--out-duplicate-metrics", out_dup_metrics_path])

    # Add BWA options
    if bwa_options:
        args.extend(["--bwa-options", bwa_options])

    # Add tool options
    if no_markdups:
        args.append("--no-markdups")

    # Add performance options
    if gpusort:
        args.append("--gpusort")
    if gpuwrite:
        args.append("--gpuwrite")
        if gpuwrite_deflate_algo:
            args.extend(["--gpuwrite-deflate-algo", str(gpuwrite_deflate_algo)])

    args.extend(["--bwa-nstreams", str(bwa_nstreams)])

    if low_memory:
        args.append("--low-memory")

    # Run the command
    returncode, stdout, stderr = await pbrun("fq2bam", args)

    if returncode != 0:
        raise RuntimeError(f"fq2bam failed with code {returncode}:\n{stderr}")

    # Upload output files
    bam_file = await File.from_local(out_bam_path)

    recal_file = None
    if out_recal_path and Path(out_recal_path).exists():
        recal_file = await File.from_local(out_recal_path)

    dup_metrics_file = None
    if out_dup_metrics_path and Path(out_dup_metrics_path).exists():
        dup_metrics_file = await File.from_local(out_dup_metrics_path)

    return Fq2BamOutputs(
        bam=bam_file,
        recal_file=recal_file,
        duplicate_metrics=dup_metrics_file,
    )


@parabricks_env.task
async def deepvariant(
    ref: File,
    in_bam: File,
    out_variants_path: str = "variants.vcf.gz",
    mode: str = "shortread",
    gvcf: bool = False,
    interval_file: Optional[File] = None,
    pb_model_file: Optional[File] = None,
    num_gpus: int = 1,
    num_streams_per_gpu: str = "auto",
    run_partition: bool = False,
) -> DeepVariantOutputs:
    """
    Run Parabricks DeepVariant for GPU-accelerated variant calling.

    DeepVariant uses deep learning to call germline variants from aligned sequencing reads.
    It can detect SNVs and InDels with high accuracy.

    Args:
        ref: Path to reference genome FASTA file
        in_bam: Input aligned BAM/CRAM file
        out_variants_path: Output VCF file path
        mode: Sequencing mode - 'shortread' (Illumina), 'pacbio', or 'ont' (Oxford Nanopore)
        gvcf: Generate variant calls in gVCF format
        interval_file: BED file for selective variant calling in specific regions
        pb_model_file: Custom Parabricks DeepVariant model file
        num_gpus: Number of GPUs to use
        num_streams_per_gpu: Number of streams per GPU ('auto' or integer)
        run_partition: Partition genome for multi-GPU parallel processing

    Returns:
        DeepVariantOutputs containing the output VCF file
    """
    # Download input files
    ref_local = await ref.download()
    bam_local = await in_bam.download()

    # Build command arguments
    args = [
        "--ref", ref_local,
        "--in-bam", bam_local,
        "--out-variants", out_variants_path,
        "--mode", mode,
        "--num-gpus", str(num_gpus),
        "--num-streams-per-gpu", str(num_streams_per_gpu),
    ]

    # Add optional arguments
    if gvcf:
        args.append("--gvcf")

    if interval_file:
        interval_local = await interval_file.download()
        args.extend(["--interval-file", interval_local])

    if pb_model_file:
        model_local = await pb_model_file.download()
        args.extend(["--pb-model-file", model_local])

    if run_partition:
        args.append("--run-partition")

    # Run the command
    returncode, stdout, stderr = await pbrun("deepvariant", args)

    if returncode != 0:
        raise RuntimeError(f"deepvariant failed with code {returncode}:\n{stderr}")

    # Upload output file
    variants_file = await File.from_local(out_variants_path)

    return DeepVariantOutputs(variants=variants_file)


@parabricks_env.task
async def haplotypecaller(
    ref: File,
    in_bam: File,
    out_variants_path: str = "variants.vcf.gz",
    in_recal_file: Optional[File] = None,
    gvcf: bool = False,
    interval_file: Optional[File] = None,
    htvc_alleles: Optional[File] = None,
    htvc_bam_output: Optional[str] = None,
    ploidy: int = 2,
    num_gpus: int = 1,
    num_htvc_threads: int = 5,
    run_partition: bool = False,
    haplotypecaller_options: Optional[str] = None,
) -> HaplotypeCallerOutputs:
    """
    Run Parabricks HaplotypeCaller for GPU-accelerated GATK-compatible variant calling.

    HaplotypeCaller calls germline SNPs and indels using local de-novo assembly of haplotypes.

    Args:
        ref: Path to reference genome FASTA file
        in_bam: Input aligned BAM/CRAM file
        out_variants_path: Output VCF file path
        in_recal_file: BQSR recalibration report to apply base quality corrections
        gvcf: Generate variant calls in gVCF format
        interval_file: Interval file (BED/Picard/GATK format) for selective calling
        htvc_alleles: VCF file with alleles to force-call regardless of evidence
        htvc_bam_output: Output BAM file path for assembled haplotypes
        ploidy: Sample ploidy (1 for haploid, 2 for diploid)
        num_gpus: Number of GPUs to use
        num_htvc_threads: Number of CPU threads per GPU
        run_partition: Partition genome for multi-GPU parallel processing
        haplotypecaller_options: Additional HaplotypeCaller options as a string

    Returns:
        HaplotypeCallerOutputs containing the output VCF and optional haplotypes BAM
    """
    # Download input files
    ref_local = await ref.download()
    bam_local = await in_bam.download()

    # Build command arguments
    args = [
        "--ref", ref_local,
        "--in-bam", bam_local,
        "--out-variants", out_variants_path,
        "--ploidy", str(ploidy),
        "--num-gpus", str(num_gpus),
        "--num-htvc-threads", str(num_htvc_threads),
    ]

    # Add optional arguments
    if in_recal_file:
        recal_local = await in_recal_file.download()
        args.extend(["--in-recal-file", recal_local])

    if gvcf:
        args.append("--gvcf")

    if interval_file:
        interval_local = await interval_file.download()
        args.extend(["--interval-file", interval_local])

    if htvc_alleles:
        alleles_local = await htvc_alleles.download()
        args.extend(["--htvc-alleles", alleles_local])

    if htvc_bam_output:
        args.extend(["--htvc-bam-output", htvc_bam_output])

    if run_partition:
        args.append("--run-partition")

    if haplotypecaller_options:
        args.extend(["--haplotypecaller-options", haplotypecaller_options])

    # Run the command
    returncode, stdout, stderr = await pbrun("haplotypecaller", args)

    if returncode != 0:
        raise RuntimeError(f"haplotypecaller failed with code {returncode}:\n{stderr}")

    # Upload output files
    variants_file = await File.from_local(out_variants_path)

    htvc_bam_file = None
    if htvc_bam_output and Path(htvc_bam_output).exists():
        htvc_bam_file = await File.from_local(htvc_bam_output)

    return HaplotypeCallerOutputs(
        variants=variants_file,
        htvc_bam=htvc_bam_file,
    )


if __name__ == "__main__":
    # Example of how to run these tasks
    flyte.init_from_config()

    # Deploy the environment to make tasks available
    flyte.deploy(parabricks_env)
