# markdup

Mark duplicated reads in a BAM/CRAM file.

This tool locates and tags duplicate reads in a BAM or SAM file, where duplicate reads are defined as originating from a single fragment of DNA.



markdup supports the marking of duplicates in two ways, assuming the sort order to be coordinate (the default) or queryname (--markdups-assume-sortorder-queryname).



The input BAM/CRAM must be sorted by queryname. If it is not, please run pbrun bamsort with --sort-order queryname to preprocess the input file. Input BAM/CRAMs must also have at least one read group line.



See the markdup Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun markdup \
    --ref /workdir/${REFERENCE_FILE} \
    --in-bam /workdir/${INPUT_BAM} \
    --out-bam /outputdir/${OUTPUT_BAM}



### Compatible Baseline Command
The command below is the GATK counterpart of the Parabricks command above. Note that the corresponding baseline command is different between marking by coordinate and by queryname. Choose the correct one based on your case. The first gatk SortSam command is listed here to guarantee the order of the input file to MarkDuplicates. Feel free to ignore it if your file order is correct.



Coordinate Sort Order


gatk SortSam \
    -R <INPUT_DIR>/${REFERENCE_FILE} \
    -I <INPUT_DIR>/${INPUT_BAM} \
    -O <INPUT_DIR>/${SORTED_BAM} \
    -SO coordinate

gatk MarkDuplicates \
    -I <INPUT_DIR>/${SORTED_BAM} \
    -O <OUTPUT_DIR>/${MARKED_BAM} \
    -M <OUTPUT_DIR>/${METRICS_FILE} \
    -ASO coordinate



Queryname Sort Order

gatk SortSam \
    -R <INPUT_DIR>/${REFERENCE_FILE} \
    -I <INPUT_DIR>/${INPUT_BAM} \
    -O <INPUT_DIR>/${SORTED_BAM} \
    -SO queryname

gatk MarkDuplicates \
    -I <INPUT_DIR>/${SORTED_BAM} \
    -O <OUTPUT_DIR>/${MARKED_BAM} \
    -M <OUTPUT_DIR>/${METRICS_FILE} \
    -ASO queryname

gatk SortSam \
    -R <INPUT_DIR>/${REFERENCE_FILE} \
    -I <OUTPUT_DIR>/${MARKED_BAM} \
    -O <OUTPUT_DIR>/${FINAL_BAM} \
    -SO coordinate



## markdup Reference
Mark duplicate reads in BAM file. The input file should be sorted by queryname.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑in‑bam IN_BAM | Yes | Path of BAM/CRAM for marking duplicate. Need to be sorted by queryname already. This option is required. |
| I/O | ‑‑out‑bam OUT_BAM | Yes | Path of BAM/CRAM file after marking duplicate. |
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑out‑duplicate‑metrics OUT_DUPLICATE_METRICS | No | Path of duplicate metrics file after marking duplicates. |
| Tool | ‑‑markdups‑assume‑sortorder‑queryname | No | Assume the reads are sorted by queryname for marking duplicates. This will mark secondary, supplementary, and unmapped reads as duplicates as well. This flag will not impact variant calling while increasing processing times. |
| Tool | ‑‑optical‑duplicate‑pixel‑distance OPTICAL_DUPLICATE_PIXEL_DISTANCE | No | The maximum offset between two duplicate clusters in order to consider them optical duplicates. |
| Tool | ‑‑markdups‑single‑ended‑start‑end | No | Mark duplicate on single-ended reads by 5' and 3' end. |
| Performance | ‑‑num‑zip‑threads NUM_ZIP_THREADS | No | Number of CPUs to use for zipping BAM/CRAM files in a run (default 10). |
| Performance | ‑‑num‑worker‑threads NUM_WORKER_THREADS | No | Number of CPUs to use for markdup in a run (default 10). |
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



