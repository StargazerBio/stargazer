# deepvariant

Run a GPU-accelerated DeepVariant algorithm.



See the deepvariant Reference section for a detailed listing of all available options.


What is DeepVariant?
DeepVariant is a deep learning based variant caller developed by Google for germline variant calling of high-throughput sequencing data. It works by taking aligned sequencing reads in BAM/CRAM format and utilizes a convolutional neural network (CNN) to classify the locus into true underlying genomic variation or sequencing error. DeepVariant can therefore call single nucleotide variants (SNVs) and insertions/deletions (InDels) from sequencing data at high accuracy in germline samples.

Why DeepVariant?
DeepVariant’s approach is able to detect variants that are often missed by traditional (for example Bayesian) variant callers, and is known to reduce false positives. It offers several advantages over similar tools, including its ability to detect a wide range of variants with high accuracy, its scalability for analyzing large datasets, and its open source availability. Additionally, its deep learning-based approach allows it to provide better support for different sequencing platforms, as it can be retrained to provide higher accuracy for specific protocols or research areas.

How should I use DeepVariant?
DeepVariant is designed for use as a germline variant caller that can apply different models trained for specific sample types (such as whole genome and whole exome samples) to yield higher accuracy results. DeepVariant can be deployed within NVIDIA’s Parabricks software suite, which is designed for accelerated secondary analysis in genomics, bringing industry standard tools and workflows from CPU to GPU, and delivering the same results at up to 60x faster runtimes. A 30x whole genome can be run through DeepVariant in as little as 8 minutes on an NVIDIA DGX station, compared to 5 hours on a CPU instance (m5.24xlarge, 96 x vCPU). DeepVariant in Parabricks is used in the same way as other command line tools that users are familiar with: It takes a BAM/CRAM and the reference genome as inputs and produces the variants (a VCF file) as outputs. Currently, DeepVariant is supported for T4 and newer GPUs out of the box.

Note
In version 3.8 the --run-partition option was added, which can lead to a significant speed increase. However, using the --run-partition, --proposed-variants, and --gvcf options at the same time will lead to a substantial slowdown. A warning will be issued and the --run-partition option will be ignored.


Available Operating Modes
Parabricks DeepVariant can run in one of three operating modes:

shortread

PacBio

ONT

See the --mode option below.


### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun deepvariant \
    --ref /workdir/${REFERENCE_FILE} \
    --in-bam /workdir/${INPUT_BAM} \
    --out-variants /outputdir/${OUTPUT_VCF}



### Compatible Google DeepVariant Commands
The commands below are the Google counterpart of the Parabricks command above. The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.

sudo docker run \
--volume <INPUT_DIR>:/input \
--volume <OUTPUT_DIR>:/output \
google/deepvariant:1.9.0 \
/opt/deepvariant/bin/run_deepvariant \
--model_type WGS \
--ref /input/${REFERENCE_FILE} \
--reads /input/${INPUT_BAM} \
--output_vcf /output/${OUTPUT_VCF} \
--num_shards $(nproc) \
--disable_small_model=true \
--make_examples_extra_args "ws_use_window_selector_model=true"


Models for additional GPUs
Parabricks DeepVariant supports the following models:

Short-read WGS

Short-read WES

PacBio

ONT

Parabricks ships with DeepVariant models for T4 and all GPUs that are Ampere or newer.

Source of Mismatches
While Parabricks DeepVariant does not lose any accuracy in functionality when compared with Google DeepVariant there is one reason that can result in different output files.

CNN Inference

Google DeepVariant uses a CNN (convolutional neural network) to predict the possibilities of each variant candidate. The model is trained, and does inference through, Keras. In Parabricks DeepVariant we convert this Keras model to an engine file with TensorRT to perform accelerated deep learning inferencing on NVIDIA GPUs. Because of the optimizations from TensorRT there is a small difference in the final possibility scores after inferencing (10^-5), which could cause a few different variants in the final VCF output. Based on current observations the mismatches only happen to RefCalls with a quality score of zero.


## deepvariant Reference
Run DeepVariant to convert BAM/CRAM to VCF.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑bam IN_BAM | Yes | Path to the input BAM/CRAM file for variant calling. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to a BED file (.bed) for selective access. This option can be used multiple times. |
| I/O | ‑‑out‑variants OUT_VARIANTS | Yes | Path of the vcf/vcf.gz/g.vcf/g.vcf.gz file after variant calling. |
| I/O | ‑‑pb‑model‑file PB_MODEL_FILE | No | Path to a non-default parabricks model file for deepvariant. |
| I/O | ‑‑proposed‑variants PROPOSED_VARIANTS | No | Path of the vcf.gz file, which has proposed variants for the make examples stage. |
| Tool | ‑‑disable‑use‑window‑selector‑model | No | Change the window selector model from Allele Count Linear to Variant Reads. This option will increase the accuracy and runtime. |
| Tool | ‑‑gvcf | No | Generate variant calls in .gvcf format. |
| Tool | ‑‑norealign‑reads | No | Do not locally realign reads before calling variants. Reads longer than 500 bp are never realigned. |
| Tool | ‑‑sort‑by‑haplotypes | No | Reads are sorted by haplotypes (using HP tag). |
| Tool | ‑‑keep‑duplicates | No | Keep reads that are duplicate. |
| Tool | ‑‑keep‑legacy‑allele‑counter‑behavior | No | If specified, the behavior in this commit is reverted: 'https://github.com/google/deepvariant/commit/fbde0674639a28cb9e8004c7a01bbe25240c7d46'. We do not recommend setting this flag to True. |
| Tool | ‑‑vsc‑min‑count‑snps VSC_MIN_COUNT_SNPS | No | SNP alleles occurring at least this many times in the AlleleCount will be advanced as candidates. (default: 2) |
| Tool | ‑‑vsc‑min‑count‑indels VSC_MIN_COUNT_INDELS | No | Indel alleles occurring at least this many times in the AlleleCount will be advanced as candidates. (default: 2) |
| Tool | ‑‑vsc‑min‑fraction‑snps VSC_MIN_FRACTION_SNPS | No | SNP alleles occurring at least this fraction of all counts in the AlleleCount will be advanced as candidates. (default: 0.12) |
| Tool | ‑‑vsc‑min‑fraction‑indels VSC_MIN_FRACTION_INDELS | No | Indel alleles occurring at least this fraction of all counts in the AlleleCount will be advanced as candidates. |
| Tool | ‑‑min‑mapping‑quality MIN_MAPPING_QUALITY | No | By default, reads with any mapping quality are kept. Setting this field to a positive integer i will only keep reads that have a MAPQ >= i. Note this only applies to aligned reads. (default: 5) |
| Tool | ‑‑min‑base‑quality MIN_BASE_QUALITY | No | Minimum base quality. This option enforces a minimum base quality score for alternate alleles. Alternate alleles will only be considered if all bases in the allele have a quality greater than min_base_quality. (default: 10) |
| Tool | ‑‑mode MODE | No | Value can be one of [shortread, pacbio, ont]. By default, it is shortread. (default: shortread) |
| Tool | ‑‑alt‑aligned‑pileup ALT_ALIGNED_PILEUP | No | Value can be one of [none, diff_channels]. Include alignments of reads against each candidate alternate allele in the pileup image. |
| Tool | ‑‑variant‑caller VARIANT_CALLER | No | Value can be one of [VERY_SENSITIVE_CALLER, VCF_CANDIDATE_IMPORTER]. The caller to use to make examples. If you use VCF_CANDIDATE_IMPORTER, it implies force calling. Default is VERY_SENSITIVE_CALLER. |
| Tool | ‑‑add‑hp‑channel | No | Add another channel to represent HP tags per read. |
| Tool | ‑‑parse‑sam‑aux‑fields | No | Auxiliary fields of the BAM/CRAM records are parsed. If either --sort-by-haplotypes or --add-hp-channel is set, then this option must also be set. |
| Tool | ‑‑use‑wes‑model | No | If specified, the WES model file will be used. Only used in shortread mode. |
| Tool | ‑‑include‑med‑dp | No | If specified, include MED_DP in the output gVCF records. |
| Tool | ‑‑normalize‑reads | No | If specified, allele counter left align INDELs for each read. |
| Tool | ‑‑pileup‑image‑width PILEUP_IMAGE_WIDTH | No | Pileup image width. Only change this if you know your model supports this width. (default: 221) |
| Tool | ‑‑channel‑insert‑size | No | If specified, add insert_size channel into the pileup image. By default, this parameter is true in WGS and WES mode. |
| Tool | ‑‑no‑channel‑insert‑size | No | If specified, don't add insert_size channel into the pileup image. |
| Tool | ‑‑max‑read‑size‑512 | No | Allow deepvariant to run on reads of size 512bp. The default size is 320 bp. |
| Tool | ‑‑prealign‑helper‑thread | No | Use an extra thread for the pre-align step. This parameter is more useful when --max-reads-size-512 is set. |
| Tool | ‑‑track‑ref‑reads | No | If specified, allele counter keeps track of reads supporting ref. By default, allele counter keeps a simple count of the number of reads supporting ref. |
| Tool | ‑‑phase‑reads | No | Calculate phases and add HP tag to all reads automatically. |
| Tool | ‑‑dbg‑min‑base‑quality DBG_MIN_BASE_QUALITY | No | Minimum base quality in a k-mer sequence to consider. (default: 15) |
| Tool | ‑‑ws‑min‑windows‑distance WS_MIN_WINDOWS_DISTANCE | No | Minimum distance between candidate windows for local assembly. (default: 80) |
| Tool | ‑‑channel‑gc‑content | No | If specified, add gc_content channel into the pileup image. |
| Tool | ‑‑channel‑hmer‑deletion‑quality | No | If specified, add hmer deletion quality channel into the pileup image. |
| Tool | ‑‑channel‑hmer‑insertion‑quality | No | If specified, add hmer insertion quality channel into the pileup image. |
| Tool | ‑‑channel‑non‑hmer‑insertion‑quality | No | If specified, add non-hmer insertion quality channel into the pileup image. |
| Tool | ‑‑skip‑bq‑channel | No | If specified, ignore base quality channel. |
| Tool | ‑‑aux‑fields‑to‑keep AUX_FIELDS_TO_KEEP | No | Comma-delimited list of auxiliary BAM fields to keep. Values can be [HP, tp, t0]. (default: HP) |
| Tool | ‑‑vsc‑min‑fraction‑hmer‑indels VSC_MIN_FRACTION_HMER_INDELS | No | Hmer Indel alleles occurring at least this be advanced as candidates. Use this threshold if hmer and non-hmer indels should be treated differently (Ultima reads)Default will use the same threshold for hmer and non-hmer indels, as defined in vsc_min_fraction_indels. |
| Tool | ‑‑vsc‑turn‑on‑non‑hmer‑ins‑proxy‑support | No | Add read-support from soft-clipped reads and other non-hmer insertion alleles,to the most frequent non-hmer insertion allele. |
| Tool | ‑‑consider‑strand‑bias | No | If specified, expect SB field in calls and write it to the VCF file. |
| Tool | ‑‑p‑error P_ERROR | No | Basecalling error for reference confidence model. (default: 0.001) |
| Tool | ‑‑channel‑ins‑size | No | If specified, add another channel to represent size of insertions (good for flow-based sequencing). |
| Tool | ‑‑max‑ins‑size MAX_INS_SIZE | No | Max insertion size for ins_size_channel, larger insertions will look like max (have max intensity). (default: 10) |
| Tool | ‑‑disable‑group‑variants | No | If using vcf_candidate_importer and multi-allelic sites are split across multiple lines in VCF, add this flag so that variants are not grouped when transforming CallVariantsOutput to Variants. |
| Tool | ‑‑filter‑reads‑too‑long | No | Ignore all input BAM reads with size > 512bp. |
| Tool | ‑‑haploid‑contigs HAPLOID_CONTIGS | No | Optional list of non autosomal chromosomes. For all listed chromosomes HET probabilities are not considered. |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to call the variants from the BAM/CRAM file. Overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Performance | ‑‑num‑cpu‑threads‑per‑stream NUM_CPU_THREADS_PER_STREAM | No | Number of CPU threads to use per stream. (default: 6) |
| Performance | ‑‑num‑streams‑per‑gpu NUM_STREAMS_PER_GPU | No | Number of streams to use per GPU. Default is 'auto' which will try to use an optimal amount of streams based on the GPU. (default: auto) |
| Performance | ‑‑run‑partition | No | Divide the whole genome into multiple partitions and run multiple processes at the same time, each on one partition. |
| Performance | ‑‑gpu‑num‑per‑partition GPU_NUM_PER_PARTITION | No | Number of GPUs to use per partition. |
| Performance | ‑‑max‑reads‑per‑partition MAX_READS_PER_PARTITION | No | The maximum number of reads per partition that are considered before following processing such as sampling and realignment. (default: 1500) |
| Performance | ‑‑partition‑size PARTITION_SIZE | No | The maximum number of basepairs allowed in a region before splitting it into multiple smaller subregions. (default: 1000) |
| Performance | ‑‑use‑tf32 | No | Enable inference optimization using Tensor Float 32(TF32) on ampere+ gpu. Note that this might introduce a few mismatches in the output VCF. |
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


