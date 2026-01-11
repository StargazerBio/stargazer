# bam2fq

Run bam2fq to convert BAM/CRAM to FASTQ.



This tool un-aligns a BAM file, reversing it from BAM to FASTQ format. This can be useful if the BAM needs to be re-aligned to a newer or different reference genome by applying bam2fq followed by fq2bam (BWA-MEM + GATK) with the new reference genome.

For paired reads, bam2fq will append "/1" to the 1st read name, and "/2" to the 2nd read name.



See the bam2fq Reference section for a detailed listing of all available options. |


### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun bam2fq \
    --ref /workdir/${REFERENCE_FILE} \
    --in-bam /workdir/${INPUT_BAM} \
    --out-prefix /workdir/${Prefix_for_output_fastq_files}



### Compatible CPU-based BWA-MEM, GATK4 Commands
The command below is the bwa-0.7.15 and GATK4 counterpart of the Parabricks command above. The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.

$ gatk SamToFastq \
    -I <INPUT_DIR>/${INPUT_BAM} \
    -F <OUTPUT_DIR>/${OUTPUT_FASTQ_1} \
    -F2 <OUTPUT_DIR>/${OUTPUT_FASTQ_2}



## bam2fq Reference
Run bam2fq to convert BAM/CRAM to FASTQ.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | No | Path to the reference file. This argument is only required for CRAM input. |
| I/O | ‑‑in‑bam IN_BAM | Yes | Path to the input BAM/CRAM file to convert to fastq.gz. |
| I/O | ‑‑out‑prefix OUT_PREFIX | Yes | Prefix filename for output FASTQ files. |
| Tool | ‑‑out‑suffixF OUT_SUFFIXF | No | Output suffix used for paired reads that are first in pair. The suffix must end with ".gz". (default: _1.fastq.gz) |
| Tool | ‑‑out‑suffixF2 OUT_SUFFIXF2 | No | Output suffix used for paired reads that are second in pair. The suffix must end with ".gz". (default: _2.fastq.gz) |
| Tool | ‑‑out‑suffixO OUT_SUFFIXO | No | Output suffix used for orphan/unmatched reads that are first in pair. The suffix must end with ".gz". If no suffix is provided, these reads will be ignored. |
| Tool | ‑‑out‑suffixO2 OUT_SUFFIXO2 | No | Output suffix used for orphan/unmatched reads that are second in pair. The suffix must end with ".gz". If no suffix is provided, these reads will be ignored. |
| Tool | ‑‑out‑suffixS OUT_SUFFIXS | No | Output suffix used for single-end/unpaired reads. The suffix must end with ".gz". If no suffix is provided, these reads will be ignored. |
| Tool | ‑‑rg‑tag RG_TAG | No | Split reads into different FASTQ files based on the read group tag. Must be either PU or ID. |
| Tool | ‑‑remove‑qc‑failure | No | Remove reads from the output that have abstract QC failure. |
| Performance | ‑‑num‑threads NUM_THREADS | No | Number of threads to run. (default: 8) |
| Runtime | ‑‑verbose | No | Enable verbose output. |
| Runtime | ‑‑x3 | No | Show full command line arguments. |
| Runtime | ‑‑logfile LOGFILE | No | Path to the log file. If not specified, messages will only be written to the standard error output. |
| Runtime | ‑‑tmp‑dir TMP_DIR | No | Full path to the directory where temporary files will be stored. (default: .) |
| Runtime | ‑‑with‑petagene‑dir WITH_PETAGENE_DIR | No | Full path to the PetaGene installation directory. By default, this should have been installed at /opt/petagene. Use of this option also requires that the PetaLink library has been preloaded by setting the LD_PRELOAD environment variable. Optionally set the PETASUITE_REFPATH and PGCLOUD_CREDPATH environment variables that are used for data and credentials. Optionally set the PetaLinkMode environment variable that is used to further configure PetaLink, notably setting it to "+write" to enable outputting compressed BAM and .fastq files. |
| Runtime | ‑‑keep‑tmp | No | Do not delete the directory storing temporary files after completion. |
| Runtime | ‑‑no‑seccomp‑override | No | Do not override seccomp options for docker. |
| Runtime | ‑‑version | No | View compatible software versions. |
| Runtime | ‑‑preserve‑file‑symlinks | No | Override default behavior to keep file symlinks intact and not resolve the symlink. |

