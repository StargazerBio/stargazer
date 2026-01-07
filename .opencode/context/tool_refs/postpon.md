# postpon

Annotate variants based on a PON file and modify the "INFO" field of the input VCF file. This is the post process of calling --pon in mutect.



See the postpon Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun postpon \
    --in-vcf /workdir/${INPUT_VCF} \
    --in-pon-file /workdir/${INPUT_PON_VCF} \
    --out-vcf /outputdir/${OUTPUT_VCF}



## postpon Reference
Annotate variants based on a PON file.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑in‑vcf IN_VCF | Yes | Path to the input VCF file. |
| I/O | ‑‑in‑pon‑file IN_PON_FILE | Yes | Path to the input PON file in vcf.gz format with its tabix index. |
| I/O | ‑‑out‑vcf OUT_VCF | Yes | Output annotated VCF file. |
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



