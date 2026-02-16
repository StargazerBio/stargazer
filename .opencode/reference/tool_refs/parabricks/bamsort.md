# bamsort

Sort BAM files.



This tool can sort the reads within a BAM file in a variety of ways, including by position in the genome (coordinate) or read name (queryname). This enables compatibility with the requirements of different downstream tools.

Five sort modes are supported:

coordinate (Picard-compatible)

coordinate (fgbio-compatible)

queryname (Picard-compatible)

queryname (fgbio-compatible)

template coordinate sort (fgbio-compatible)

Allowed values for --sort-order are as follows:

coordinate [default]

queryname

templatecoordinate

Allowed values for --sort-compatibility are as follows:

picard [default]

fgbio

coordinate and queryname sorting can be done in either picard or fgbio mode. templatecoordinate can only be done in fgbio mode.



See the bamsort Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun bamsort \
    --ref /workdir/${REFERENCE_FILE} \
    --in-bam /workdir/${INPUT_BAM} \
    --out-bam /outputdir/${OUTPUT_BAM} \
    --sort-order coordinate



### Compatible Picard Command
The command below is the Picard counterpart of the Parabricks command above. The output from this command will be identical to the output from the above command.

$ java -Xmx30g -jar picard.jar SortSam \
    I=<INPUT_DIR>/${INPUT_BAM} \
    O=<OUTPUT_DIR>/${OUTPUT_BAM}



## bamsort Reference
Sort BAM files. There are five modes: Coordinate sort (Picard-compatible), Coordinate sort (fgbio-compatible), queryname sort (Picard-compatible), queryname sort (fgbio-compatible), and template coordinate sort (fgbio- compatible).




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑in‑bam IN_BAM | Yes | Path of BAM/CRAM for sorting. This option is required. |
| I/O | ‑‑out‑bam OUT_BAM | Yes | Path of BAM/CRAM file after sorting. |
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| Tool | ‑‑sort‑order SORT_ORDER | No | Type of sort to be done. Possible values are {coordinate,queryname,templatecoordinate}. (default: coordinate) |
| Tool | ‑‑sort‑compatibility SORT_COMPATIBILITY | No | Sort comparator compatibility to be used for compatibility with other tools. Possible values are {picard,fgbio}. TemplateCoordinate will only use fgbio. (default: picard) |
| Performance | ‑‑num‑zip‑threads NUM_ZIP_THREADS | No | Number of CPUs to use for zipping BAM files in a run (default 16 for coordinate sorts and 10 otherwise). |
| Performance | ‑‑num‑sort‑threads NUM_SORT_THREADS | No | Number of CPUs to use for sorting in a run (default 10 for coordinate sorts and 16 otherwise). |
| Performance | ‑‑max‑records‑in‑ram MAX_RECORDS_IN_RAM | No | Maximum number of records in RAM when using a queryname or template coordinate sort mode; lowering this number will decrease maximum memory usage. (default: 65000000) |
| Performance | ‑‑mem‑limit MEM_LIMIT | No | Memory limit in GBs during sorting and postsorting. By default, the limit is half of the total system memory. (default: 62) |
| Performance | ‑‑gpuwrite | No | Use one GPU to accelerate writing final BAM/CRAM. |
| Performance | ‑‑gpuwrite‑deflate‑algo GPUWRITE_DEFLATE_ALGO | No | Choose the nvCOMP DEFLATE algorithm to use with --gpuwrite. Note these options do not correspond to CPU DEFLATE options. Valid options are 1, 2, and 4. Option 1 is fastest, while options 2 and 4 have progressively lower throughput but higher compression ratios. The default value is 1 when the user does not provide an input (i.e., None) |
| Performance | ‑‑gpusort | No | Use GPUs to accelerate sorting and marking. |
| Runtime | ‑‑verbose | No | Enable verbose output. |
| Runtime | ‑‑x3 | No | Show full command line arguments. |
| Runtime | ‑‑logfile LOGFILE | No | Path to the log file. If not specified, messages will only be written to the standard error output. |
| Runtime | ‑‑tmp‑dir TMP_DIR | No | Full path to the directory where temporary files will be stored. (default: .) |
| Runtime | ‑‑with‑petagene‑dir WITH_PETAGENE_DIR | No | Full path to the PetaGene installation directory. By default, this should have been installed at /opt/petagene. Use of this option also requires that the PetaLink library has been preloaded by setting the LD_PRELOAD environment variable. Optionally set the PETASUITE_REFPATH and PGCLOUD_CREDPATH environment variables that are used for data and credentials. Optionally set the PetaLinkMode environment variable that is used to further configure PetaLink, notably setting it to "+write" to enable outputting compressed BAM and .fastq files. |
| Runtime | ‑‑keep‑tmp | No | Do not delete the directory storing temporary files after completion. |
| Runtime | ‑‑no‑seccomp‑override | No | Do not override seccomp options for docker. |
| Runtime | ‑‑version | No | View compatible software versions. |
| Runtime | ‑‑preserve‑file‑symlinks | No | Override default behavior to keep file symlinks intact and not resolve the symlink. |



