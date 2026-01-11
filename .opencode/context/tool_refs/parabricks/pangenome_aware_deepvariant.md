# pangenome_aware_deepvariant

Run a GPU-accelerated Pangenome-aware DeepVariant algorithm.



See the pangenome_aware_deepvariant Reference section for a detailed listing of all available options.


What is Pangenome-aware DeepVariant?
Pangenome-aware DeepVariant is an enhanced version of Google's DeepVariant that leverages pangenome reference graphs (GBZ files) to improve variant calling accuracy, particularly in complex and highly variable genomic regions. Traditional variant calling pipelines use a single linear reference genome, which can miss variants in regions that differ significantly from the reference. Pangenome-aware DeepVariant uses pangenome graphs that represent multiple haplotypes and structural variations, enabling more accurate variant detection in diverse populations. Like DeepVariant, Pangenome-aware Deepvariant generates pileup images and uses a CNN to infer genotypes. However, unlike DeepVariant, pileup images are generated for both the input reads and the pangenome haplotypes at potential variant positions. This allows directly using a pangenome for identifying true variants.

Why Pangenome-aware DeepVariant?
Linear genome references have been the standard for reference-based genomic analysis. However, linear references can introduce reference bias where the reference geneome is significantly different from the sample under study. Using a pangenome reference is one way to address this issue, since it includes diverse, non-redundant DNA sequences from multiple individuals. Pangenome-aware Deepvariant leverages the pangenome reference to outperform linear-reference-based DeepVariant by upto 25.5% across various short-read sequencing platforms and read mappers. Researchers from Google have also shown that Element reads with pangenome-aware DeepVariant can achieve 23.6% more accurate variant calling performance compared to existing methods.


### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun pangenome_aware_deepvariant \
    --ref /workdir/${REFERENCE_FILE} \
    --pangenome /workdir/${GBZ_FILE} \
    --in-bam /workdir/${INPUT_BAM} \
    --out-variants /outputdir/${OUTPUT_VCF}



### Compatible Google pangenome-aware DeepVariant Command
The command below shows the equivalent Google pangenome-aware DeepVariant command. Note that the Parabricks version provides the same accuracy with significant GPU acceleration.

sudo docker run \
--volume <INPUT_DIR>:/input \
--volume <OUTPUT_DIR>:/output \
--shm-size 12gb \
google/pangenome_aware_deepvariant-1.9.0 \
/opt/deepvariant/bin/run_pangenome_aware_deepvariant \
--model_type WGS \
--ref /input/${REFERENCE_FILE} \
--reads /input/${INPUT_BAM} \
--pangenome /input/${GBZ_FILE} \
--output_vcf /output/${OUTPUT_VCF} \
--num_shards $(nproc) \
--make_examples_extra_args "ws_use_window_selector_model=true"


Source of Mismatches
While Parabricks Pangenome-aware DeepVariant does not lose any accuracy in functionality when compared with Google's Pangenome-aware DeepVariant, there are several reasons that can result in different output files:

CNN Inference

Google DeepVariant uses a CNN (convolutional neural network) to predict the possibilities of each variant candidate. The model is trained, and does inference through, Keras. In Parabricks DeepVariant we convert this Keras model to an engine file with TensorRT to perform accelerated deep learning inferencing on NVIDIA GPUs. Because of the optimizations from TensorRT there is a small difference in the final possibility scores after inferencing (10^-5), which could cause a few different variants in the final VCF output. Based on current observations the mismatches only happen to RefCalls with a quality score of zero.

Read Sorting Differences

The Google Pangenome-aware DeepVariant implementation uses sort instead of stable_sort for sorting reads based on position, fragment_name, and read_number. Unfortunately, when the keep-supplementary-alignments option is enabled, it is possible to have duplicate reads which are sorted non-deterministically by std::sort. The Parabricks implementation uses stable_sort to resolve this. To obtain identical results with Google's implementation, users are recommended to update the std::sort in BuildPileupForOneSample pileup_image_native.cc to std::stable_sort.

GBZ Reader Caching Mechanism

Google Pangenome-aware DeepVariant's GBZ reader includes a fast path to speed up queries to the pangenome graph. This fast path introduces non-determinism in the query operation to the pangenome where the result returned by the operation depends on the order of the previous queries to the pangenome. Since, Parabricks relies on multi-threading to achieve high performance, we disable the fast path in the Parabricks implementation. To obtain identical results using Google's implementation, users should comment out the call to updateCache in the GbzReader::Query() function in deepvariant/third_party/nucleus/io/gbz_reader.cc. Also, the check for whether the requested range is cached or not should be disabled (in the same function). Please note that disabling the cache can slow down Google Deepvariant significantly and is not recommended in general. We suggest this approach only for the purposes of comparing output accuracy.


## pangenome_aware_deepvariant Reference
Run pangenome_aware_deepvariant to convert BAM/CRAM to VCF.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑pangenome PANGENOME | Yes | Path to the pangenome gbz file. |
| I/O | ‑‑in‑bam IN_BAM | Yes | Path to the input BAM/CRAM file for variant calling. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to a BED file (.bed) for selective access. This option can be used multiple times. |
| I/O | ‑‑out‑variants OUT_VARIANTS | Yes | Path of the vcf/vcf.gz/g.vcf/g.vcf.gz file after variant calling. |
| I/O | ‑‑pb‑model‑file PB_MODEL_FILE | No | Path to a non-default parabricks model file for pangenome_aware_deepvariant. |
| Tool | ‑‑disable‑use‑window‑selector‑model | No | Change the window selector model from Allele Count Linear to Variant Reads. This option will increase the accuracy and runtime. |
| Tool | ‑‑norealign‑reads | No | Do not locally realign reads before calling variants. Reads longer than 500 bp are never realigned. |
| Tool | ‑‑min‑mapping‑quality MIN_MAPPING_QUALITY | No | By default, reads with any mapping quality are kept. Setting this field to a positive integer i will only keep reads that have a MAPQ >= i. Note this only applies to aligned reads. |
| Tool | ‑‑mode MODE | No | Value can be one of [shortread]. By default, it is shortread. (default: shortread) |
| Tool | ‑‑pileup‑image‑width PILEUP_IMAGE_WIDTH | No | Pileup image width. Only change this if you know your model supports this width. |
| Tool | ‑‑no‑channel‑insert‑size | No | If True, don't add insert_size channel into the pileup image. (default: False) |
| Tool | ‑‑sample‑name‑pangenome SAMPLE_NAME_PANGENOME | No | Sample name to use for pangenome data. Default is 'pangenome'. (default: pangenome) |
| Tool | ‑‑ref‑name‑pangenome REF_NAME_PANGENOME | No | Reference genome name for pangenome data. Default is 'GRCh38'. (default: GRCh38) |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to call the variants from the BAM/CRAM file. Overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Performance | ‑‑num‑cpu‑threads‑per‑stream NUM_CPU_THREADS_PER_STREAM | No | Number of CPU threads to use per stream. (default: 6) |
| Performance | ‑‑num‑streams‑per‑gpu NUM_STREAMS_PER_GPU | No | Number of streams to use per GPU. Default is 'auto' which will try to use an optimal amount of streams based on the GPU. (default: auto) |
| Performance | ‑‑run‑partition | No | Divide the whole genome into multiple partitions and run multiple processes at the same time, each on one partition. |
| Performance | ‑‑gpu‑num‑per‑partition GPU_NUM_PER_PARTITION | No | Number of GPUs to use per partition. |
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



