# starfusion

Identifies candidate fusion transcripts.



This tool performs fusion calling for RNA-Seq samples, utilizing the STAR-Fusion algorithm. This requires input of a genome resource library, in accordance with the original STAR-Fusion tool, and outputs candidate fusion transcripts.



See the starfusion Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun starfusion \
    --chimeric-junction /workdir/${CHIMERIC_JUNCTION_INPUT} \
    --genome-lib-dir /workdir/${PATH_TO_GENOME_LIBRARY}/ \
    --output-dir /outputdir/${PATH_TO_OUTPUT_DIRECTORY}/



### Compatible CPU Command
The command below is the CPU counterpart of the Parabricks command above. The output from this command will be identical to the output from the above command.

$ ./STAR-Fusion \
    --chimeric_junction <INPUT_DIR>/${CHIMERIC_JUNCTION_INPUT} \
    --genome_lib_dir <INPUT_DIR>/${PATH_TO_GENOME_LIBRARY} \
    --output_dir <OUTPUT_DIR>/${PATH_TO_OUTPUT_DIRECTORY}



## starfusion Reference
Identify candidate fusion transcripts supported by Illumina reads.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑chimeric‑junction CHIMERIC_JUNCTION | Yes | Path to the Chimeric.out.junction file produced by STAR. |
| I/O | ‑‑genome‑lib‑dir GENOME_LIB_DIR | Yes | Path to a genome resource library directory. For more information, visit https://github.com/STAR-Fusion/STAR-Fusion/wiki/installing-star-fusion#data-resources-required. |
| I/O | ‑‑output‑dir OUTPUT_DIR | Yes | Path to the directory that will contain all of the generated files. |
| Tool | ‑‑out‑prefix OUT_PREFIX | No | Prefix filename for output data. |
| Performance | ‑‑num‑threads NUM_THREADS | No | Number of threads for worker. (default: 4) |
| Runtime | ‑‑verbose | No | Enable verbose output. |
| Runtime | ‑‑x3 | No | Show full command line arguments. |
| Runtime | ‑‑logfile LOGFILE | No | Path to the log file. If not specified, messages will only be written to the standard error output. |
| Runtime | ‑‑tmp‑dir TMP_DIR | No | Full path to the directory where temporary files will be stored. (default: .) |
| Runtime | ‑‑with‑petagene‑dir WITH_PETAGENE_DIR | No | Full path to the PetaGene installation directory. By default, this should have been installed at /opt/petagene. Use of this option also requires that the PetaLink library has been preloaded by setting the LD_PRELOAD environment variable. Optionally set the PETASUITE_REFPATH and PGCLOUD_CREDPATH environment variables that are used for data and credentials. Optionally set the PetaLinkMode environment variable that is used to further configure PetaLink, notably setting it to "+write" to enable outputting compressed BAM and .fastq files. |
| Runtime | ‑‑keep‑tmp | No | Do not delete the directory storing temporary files after completion. |
| Runtime | ‑‑no‑seccomp‑override | No | Do not override seccomp options for docker. |
| Runtime | ‑‑version | No | View compatible software versions. |
| Runtime | ‑‑preserve‑file‑symlinks | No | Override default behavior to keep file symlinks intact and not resolve the symlink. |