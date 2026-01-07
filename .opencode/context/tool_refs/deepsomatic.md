# deepsomatic

GPU-accelerated DeepSomatic


What is DeepSomatic?
DeepSomatic builds on the deep learning-based variant caller DeepVariant. It processes aligned reads from tumor and normal samples (in BAM or CRAM format), generates pileup image tensors, classifies these tensors using a convolutional neural network, and outputs somatic variants in standard VCF or gVCF files.

DeepSomatic is designed for somatic variant calling using tumor-normal sequencing data.

Parabricks has enhanced Google DeepSomatic to leverage GPUs extensively. The Parabricks version of DeepSomatic operates similarly to other common command line tools: it accepts two BAM files and a reference file as inputs and generates variants in a VCF file as output.



See the deepsomatic Reference section for a detailed listing of all available options.




### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun deepsomatic \
    --ref /workdir/${REFERENCE_FILE} \
    --in-tumor-bam /workdir/${INPUT_TUMOR_BAM} \
    --in-normal-bam /workdir/${INPUT_NORMAL_BAM} \
    --out-variants /outputdir/${OUTPUT_VCF}



### Compatible Google DeepSomatic Commands
The commands below are the Google counterpart of the Parabricks command above. The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.

docker run \
--interactve \
--tty \
--rm \
--volume ${INPUT_DIR}:${INPUT_DIR} \
--volume ${OUTPUT_DIR}:${OUTPUT_DIR} \
--workdir /workdir google/deepsomatic:1.9.0 \
run_deepsomatic \
--ref ${REFERENCE_FILE} \
--reads_tumor ${TUMOR_BAM} \
--reads_normal ${NORMAL_BAM}  \
--model_type=WGS \
--output_vcf ${OUTPUT_VCF} \
--make_examples_extra_args "ws_use_window_selector_model=true" \
--num_shards=$(nproc)


Models for additional GPUs
Parabricks DeepSomatic supports the following models:

Short-read WGS

Short-read WES

PacBio

ONT

Source of Mismatches
While Parabricks DeepSomatic does not lose any accuracy in functionality when compared with Google DeepSomatic there is one reason that can result in different output files.

CNN Inference

Google DeepSomatic uses a CNN (convolutional neural network) to predict the possibilities of each variant candidate. The model is trained, and does inference through, Keras. In Parabricks DeepSomatic we convert this Keras model to an engine file with TensorRT to perform accelerated deep learning inferencing on NVIDIA GPUs. Because of the optimizations from TensorRT there is a small difference in the final possibility scores after inferencing (10^-5), which could cause a few different variants in the final VCF output. Based on current observations the mismatches only happen to RefCalls with a quality score of zero.


## deepsomatic Reference
Run DeepSomatic to convert BAM/CRAM to VCF.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑tumor‑bam IN_TUMOR_BAM | Yes | Path to the input tumor BAM/CRAM file for somatic variant calling. |
| I/O | ‑‑in‑normal‑bam IN_NORMAL_BAM | Yes | Path to the input normal BAM/CRAM file for somatic variant calling. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to a BED file (.bed) for selective access. This option can be used multiple times. |
| I/O | ‑‑out‑variants OUT_VARIANTS | Yes | Path of the vcf/vcf.gz/g.vcf/g.vcf.gz file after variant calling. |
| I/O | ‑‑pb‑model‑file PB_MODEL_FILE | No | Path to a non-default parabricks model file for deepsomatic. |
| Tool | ‑‑disable‑use‑window‑selector‑model | No | Change the window selector model from Allele Count Linear to Variant Reads. This option will increase the accuracy and runtime. |
| Tool | ‑‑norealign‑reads | No | Do not locally realign reads before calling variants. Reads longer than 500 bp are never realigned. |
| Tool | ‑‑sort‑by‑haplotypes | No | Reads are sorted by haplotypes (using HP tag). |
| Tool | ‑‑vsc‑min‑count‑snps VSC_MIN_COUNT_SNPS | No | SNP alleles occurring at least this many times in the AlleleCount will be advanced as candidates. |
| Tool | ‑‑vsc‑min‑count‑indels VSC_MIN_COUNT_INDELS | No | Indel alleles occurring at least this many times in the AlleleCount will be advanced as candidates. |
| Tool | ‑‑vsc‑min‑fraction‑snps VSC_MIN_FRACTION_SNPS | No | SNP alleles occurring at least this fraction of all counts in the AlleleCount will be advanced as candidates. |
| Tool | ‑‑vsc‑min‑fraction‑indels VSC_MIN_FRACTION_INDELS | No | Indel alleles occurring at least this fraction of all counts in the AlleleCount will be advanced as candidates. |
| Tool | ‑‑min‑mapping‑quality MIN_MAPPING_QUALITY | No | By default, reads with any mapping quality are kept. Setting this field to a positive integer i will only keep reads that have a MAPQ >= i. Note this only applies to aligned reads. |
| Tool | ‑‑mode MODE | No | Value can be one of [shortread, pacbio, ont]. By default, it is shortread. (default: shortread) |
| Tool | ‑‑alt‑aligned‑pileup ALT_ALIGNED_PILEUP | No | Value can be one of [none, diff_channels]. Include alignments of reads against each candidate alternate allele in the pileup image. |
| Tool | ‑‑add‑hp‑channel | No | Add another channel to represent HP tags per read. |
| Tool | ‑‑parse‑sam‑aux‑fields | No | Auxiliary fields of the BAM/CRAM records are parsed. If either --sort-by-haplotypes or --add-hp-channel is set, then this option must also be set. |
| Tool | ‑‑use‑wes‑model | No | If passed, the WES model file will be used. Only used in shortread mode. |
| Tool | ‑‑pileup‑image‑width PILEUP_IMAGE_WIDTH | No | Pileup image width. Only change this if you know your model supports this width. |
| Tool | ‑‑no‑channel‑insert‑size | No | If True, don't add insert_size channel into the pileup image. (default: False) |
| Tool | ‑‑track‑ref‑reads | No | If True, allele counter keeps track of reads supporting ref. By default, allele counter keeps a simple count of the number of reads supporting ref. |
| Tool | ‑‑phase‑reads | No | Calculate phases and add HP tag to all reads automatically. |
| Tool | ‑‑vsc‑max‑fraction‑indels‑for‑non‑target‑sample VSC_MAX_FRACTION_INDELS_FOR_NON_TARGET_SAMPLE | No | Maximum fraction of indels allowed in non-target samples. (default: 0.5) |
| Tool | ‑‑vsc‑max‑fraction‑snps‑for‑non‑target‑sample VSC_MAX_FRACTION_SNPS_FOR_NON_TARGET_SAMPLE | No | Maximum fraction of snps allowed in non-target samples. (default: 0.5) |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to call the variants from the BAM/CRAM file. Overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Performance | ‑‑num‑cpu‑threads‑per‑stream NUM_CPU_THREADS_PER_STREAM | No | Number of CPU threads to use per stream. (default: 6) |
| Performance | ‑‑num‑streams‑per‑gpu NUM_STREAMS_PER_GPU | No | Number of streams to use per GPU. Default is 'auto' which will try to use an optimal amount of streams based on the GPU. (default: auto) |
| Performance | ‑‑run‑partition | No | Divide the whole genome into multiple partitions and run multiple processes at the same time, each on one partition. |
| Performance | ‑‑gpu‑num‑per‑partition GPU_NUM_PER_PARTITION | No | Number of GPUs to use per partition. |
| Performance | ‑‑partition‑size PARTITION_SIZE | No | The maximum number of basepairs allowed in a region before splitting it into multiple smaller subregions. |
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


