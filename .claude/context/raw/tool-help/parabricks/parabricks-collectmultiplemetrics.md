# collectmultiplemetrics

Run a GPU-accelerated version of GATK’s CollectMultipleMetrics.



This tool applies an accelerated version of the GATK CollectMultipleMetrics for assessing BAM file metrics such as alignment success, quality score distributions, GC bias, and sequencing artifacts. This functions as a ‘meta-metrics’ tool that can run any combination of the available metrics tools in GATK to perform an overall assessment of how well a sequencing run has been performed. The available metrics tools (PROGRAMs) can be found in the reference section below.



See the collectmultiplemetrics Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun collectmultiplemetrics \
    --ref /workdir/${REFERENCE_FILE} \
    --bam /workdir/${INPUT_BAM} \
    --out-qc-metrics-dir /outputdir/${OUTPUT_DIR}\
    --gen-all-metrics



### Compatible GATK4 Command
The command below is the GATK4 counterpart of the Parabricks command above. The output from this command will be identical to the output from the above command.

$ gatk CollectMultipleMetrics \
--REFERENCE_SEQUENCE <INPUT_DIR>/${REFERENCE_FILE} \
-I <INPUT_DIR>/${INPUT_BAM} \
-O <OUTPUT_DIR>/${OUTPUT_DIR} \
--PROGRAM CollectAlignmentSummaryMetrics \
--PROGRAM CollectInsertSizeMetrics \
--PROGRAM QualityScoreDistribution \
--PROGRAM MeanQualityByCycle \
--PROGRAM CollectBaseDistributionByCycle \
--PROGRAM CollectGcBiasMetrics \
--PROGRAM CollectSequencingArtifactMetrics \
--PROGRAM CollectQualityYieldMetrics



## collectmultiplemetrics Reference
Run collectmultiplemetrics on a BAM file to generate files for multiple classes of metrics.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑bam BAM | Yes | Path to the BAM file. |
| I/O | ‑‑out‑qc‑metrics‑dir OUT_QC_METRICS_DIR | Yes | Output Directory to store results of each analysis. |
| Tool | ‑‑gen‑all‑metrics | No | Generate QC for every analysis. |
| Tool | ‑‑gen‑alignment | No | Generate QC for alignment summary metric. |
| Tool | ‑‑gen‑quality‑score | No | Generate QC for quality score distribution metric. |
| Tool | ‑‑gen‑insert‑size | No | Generate QC for insert size metric. |
| Tool | ‑‑gen‑mean‑quality‑by‑cycle | No | Generate QC for mean quality by cycle metric. |
| Tool | ‑‑gen‑base‑distribution‑by‑cycle | No | Generate QC for base distribution by cycle metric. |
| Tool | ‑‑gen‑gc‑bias | No | Prefix name used to generate detail and summary files for gc bias metric. |
| Tool | ‑‑gen‑seq‑artifact | No | Generate QC for sequencing artifact metric. |
| Tool | ‑‑gen‑quality‑yield | No | Generate QC for quality yield metric. |
| Performance | ‑‑bam‑decompressor‑threads BAM_DECOMPRESSOR_THREADS | No | Number of threads for BAM decompression. (default: 3) |
| Runtime | ‑‑verbose | No | Enable verbose output. |
| Runtime | ‑‑x3 | No | Show full command line arguments. |
| Runtime | ‑‑logfile LOGFILE | No | Path to the log file. If not specified, messages will only be written to the standard error output. |
| Runtime | ‑‑tmp‑dir TMP_DIR | No | Full path to the directory where temporary files will be stored. (default: .) |
| Runtime | ‑‑with‑petagene‑dir WITH_PETAGENE_DIR | No | Full path to the PetaGene installation directory. By default, this should have been installed at /opt/petagene. Use of this option also requires that the PetaLink library has been preloaded by setting the LD_PRELOAD environment variable. Optionally set the PETASUITE_REFPATH and PGCLOUD_CREDPATH environment variables that are used for data and credentials. Optionally set the PetaLinkMode environment variable that is used to further configure PetaLink, notably setting it to "+write" to enable outputting compressed BAM and .fastq files. |
| Runtime | ‑‑keep‑tmp | No | Do not delete the directory storing temporary files after completion. |
| Runtime | ‑‑no‑seccomp‑override | No | Do not override seccomp options for docker. |
| Runtime | ‑‑version | No | View compatible software versions. |
| Runtime | ‑‑preserve‑file‑symlinks | No | Override default behavior to keep file symlinks intact and not resolve the symlink. |
| Runtime | ‑‑num‑gpus NUM_GPUS | No | Number of GPUs to use for a run. (default: 1) |



