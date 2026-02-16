# bqsr

This tool generates a Base Quality Score Recalibration report, which can be applied by the applybqsr tool, to recalibrate the quality scores in a BAM file. This is applied as part of the recommended GATK best practices to maximize accuracy in variant calling.



See the bqsr Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
     --workdir /workdir \
     nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
     pbrun bqsr \
     --ref /workdir/${REFERENCE_FILE} \
     --in-bam /workdir/${INPUT_BAM} \
     --knownSites /workdir/${KNOWN_SITES_FILE} \
     --out-recal-file /outputdir/${INPUT_RECAL_FILE} \



### Compatible GATK4 Command
The command below is the GATK4 counterpart of the Parabricks command above. The output from this command will be identical to the output from the above command.

$ gatk BaseRecalibrator \
    --java-options -Xmx30g \
    --input <INPUT_DIR>/${INPUT_BAM} \
    --output <OUTPUT_DIR>/${INPUT_RECAL_FILE} \
    --known-sites <INPUT_DIR>/${KNOWN_SITES_FILE} \
    --reference <INPUT_DIR>/${REFERENCE_FILE}



## bqsr Reference
Run BQSR on a BAM file to generate a BQSR report.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑bam IN_BAM | Yes | Path to the BAM file. |
| I/O | ‑‑knownSites KNOWNSITES | Yes | Path to a known indels file. The file must be in vcf.gz format. This option can be used multiple times. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to an interval file in one of these formats: Picard-style (.interval_list or .picard), GATK-style (.list or .intervals), or BED file (.bed). This option can be used multiple times. |
| I/O | ‑‑out‑recal‑file OUT_RECAL_FILE | Yes | Output Report File. |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to call BQSR from the input reads. All intervals will have a padding of 100 to get read records, and overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Tool | ‑ip INTERVAL_PADDING, ‑‑interval‑padding INTERVAL_PADDING | No | Amount of padding (in base pairs) to add to each interval you are including. |
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



