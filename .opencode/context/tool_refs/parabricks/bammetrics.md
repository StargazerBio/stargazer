# bammetrics

Accelerated GATK4 CollectWGSMetrics.



This tool applies an accelerated version of the GATK CollectWGSMetrics for assessing coverage and quality of an aligned whole-genome BAM file. This includes metrics such as the fraction of reads that pass the base and mapping quality filters, and the coverage levels (read-depth) across the genome. These act as an overall quality check for the user, allowing assessment of how well a sequencing run has performed.



See the bammetrics Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun bammetrics \
    --ref /workdir/${REFERENCE_FILE} \
    --bam /workdir/${INPUT_BAM} \
    --out-metrics-file /outputdir/${METRICS_FILE}



### Compatible GATK4 Command
The command below is the GATK4 counterpart of the Parabricks command above. The output from this command will be identical to the output from the above command.

$ gatk CollectWgsMetrics \
    -R <INPUT_DIR>/${REFERENCE_FILE} \
    -I <INPUT_DIR>/${INPUT_BAM} \
    -O <OUTPUT_DIR>/${METRICS_FILE}



## bammetrics Reference
Run bammetrics on a BAM file to generate a metrics file.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑bam BAM | Yes | Path to the BAM file. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to an interval file in one of these formats: Picard-style (.interval_list or .picard), GATK-style (.list or .intervals), or BED file (.bed). This option can be used multiple times. |
| I/O | ‑‑out‑metrics‑file OUT_METRICS_FILE | Yes | Output Metrics File. |
| Tool | ‑‑minimum‑base‑quality MINIMUM_BASE_QUALITY | No | Minimum base quality for a base to contribute coverage. (default: 20) |
| Tool | ‑‑minimum‑mapping‑quality MINIMUM_MAPPING_QUALITY | No | Minimum mapping quality for a read to contribute coverage. (default: 20) |
| Tool | ‑‑count‑unpaired | No | If specified, count unpaired reads and paired reads with one end unmapped. |
| Tool | ‑‑coverage‑cap COVERAGE_CAP | No | Treat positions with coverage exceeding this value as if they had coverage at this value (but calculate the difference for PCT_EXC_CAPPED). (default: 250) |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to collect metrics from the BAM/CRAM file. All intervals will have a padding of 0 to get read records, and overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Performance | ‑‑num‑threads NUM_THREADS | No | Number of threads to run. (default: 12) |
| Runtime | ‑‑verbose | No | Enable verbose output. |
| Runtime | ‑‑x3 | No | Show full command line arguments. |
| Runtime | ‑‑logfile LOGFILE | No | Path to the log file. If not specified, messages will only be written to the standard error output. |
| Runtime | ‑‑tmp‑dir TMP_DIR | No | Full path to the directory where temporary files will be stored. (default: .) |
| Runtime | ‑‑with‑petagene‑dir WITH_PETAGENE_DIR | No | Full path to the PetaGene installation directory. By default, this should have been installed at /opt/petagene. Use of this option also requires that the PetaLink library has been preloaded by setting the LD_PRELOAD environment variable. Optionally set the PETASUITE_REFPATH and PGCLOUD_CREDPATH environment variables that are used for data and credentials. Optionally set the PetaLinkMode environment variable that is used to further configure PetaLink, notably setting it to "+write" to enable outputting compressed BAM and .fastq files. |
| Runtime | ‑‑keep‑tmp | No | Do not delete the directory storing temporary files after completion. |
| Runtime | ‑‑no‑seccomp‑override | No | Do not override seccomp options for docker. |
| Runtime | ‑‑version | No | View compatible software versions. |
| Runtime | ‑‑preserve‑file‑symlinks | No | Override default behavior to keep file symlinks intact and not resolve the symlink. |


