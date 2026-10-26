# haplotypecaller

Run a GPU-accelerated haplotypecaller.



This tool applies an accelerated GATK CollectMultipleMetrics for assessing the metrics of a BAM file, such as including alignment success, quality score distributions, GC bias, and sequencing artifacts. This functions as a ‘meta-metrics’ tool, and can run any combination of the available metrics tools in GATK to assess overall how well a sequencing run has performed. The available metrics tools (PROGRAMs) can be found in the command line example below.

You can provide an optional BQSR report to fix the BAM, similar to ApplyBQSR. In this case, the updated base qualities will be used.


parabricks-web-graphics-1259949-r2-haplotypecaller.svg


See the haplotypecaller Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun haplotypecaller \
    --ref /workdir/${REFERENCE_FILE} \
    --in-bam /workdir/${INPUT_BAM_FILE} \
    --in-recal-file /workdir/${INPUT_RECAL_FILE} \
    --out-variants /outputdir/${OUTPUT_VCF_FILE}



### Compatible GATK4 Command
The commands below are the GATK4 counterpart of the Parabricks command above. The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.

# Run ApplyBQSR Step
$ gatk ApplyBQSR \
    --java-options -Xmx30g \
    -R Ref/Homo_sapiens_assembly38.fasta \
    -I mark_dups_cpu.bam \
    --bqsr-recal-file recal_file.txt \
    -O cpu_nodups_BQSR.bam

#Run Haplotype Caller
$ gatk HaplotypeCaller \
    --java-options -Xmx30g \
    --input cpu_nodups_BQSR.bam \
    --output result_cpu.vcf \
    --reference Ref/Homo_sapiens_assembly38.fasta \
    --native-pair-hmm-threads 16


Source of Mismatches
While the Parabricks HaplotypeCaller does not lose any accuracy in functionality when compared with the GATK HaplotypeCaller there are a few implementation differences that can result in slightly different output files.

Random generator

The GATK HapltoypeCaller calls the same random generator in read downsampling and QualByDepth annotation computation. The Parabricks HaplotypeCaller calls two separate random number generators to allow for parallel computing.

Log10 implementation

The log10 operation is used to compute the haplotype penalty score. The Java implementation java.lang.Math.log10() is slightly different from the C++ cmath library, giving rise to small mismatches in computed scores. Different haplotypes might be selected because of this.

AVX

GATK calls Intel GKL (Genomics Kernel Library) which contains optimized versions of compute kernels (e.g. Smith-Waterman, PairHMM) to run on Intel Architecture (AVX, AVX2, AVX-512, and multicore). However, some SIMD intrinsics such as _mm512_mul_ps can generate a slightly different output when compared with the serial operations which our GPU implementation is based on.

HashMap, HashSet iteration

GATK can give non-deterministic outputs because iterating over a Java HashMap or HashSet does not preserve order. Parabricks always gives deterministic output by using a hash table that preserves the insertion order (similar to LinkedHashMap in Java).

Specifying Haplotype Caller options
Several original HaplotypeCaller options are supported by Parabricks. To specify the inclusion or exclusion of several haplotype caller annotations, use the --haplotypecaller-options option:

$ # This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
     --workdir /workdir \
     nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
     pbrun haplotypecaller \
      ...
      --haplotypecaller-options '-min-pruning 4 -A AS_BaseQualityRankSumTest -A TandemRepeat'
      ...


Annotations may be excluded in the same manner using the -AX option. There should be a space between the -A/-AX flag and its value.

The following are supported options and their allowed values:

-A
AS_BaseQualityRankSumTest

AS_FisherStrand

AS_InbreedingCoeff

AS_MappingQualityRankSumTest

AS_QualByDepth

AS_RMSMappingQuality

AS_ReadPosRankSumTest

AS_StrandOddsRatio

AssemblyComplexity

BaseQualityRankSumTest

ChromosomeCounts

ClippingRankSumTest

Coverage

DepthPerAlleleBySample

DepthPerSampleHC

ExcessHet

FisherStrand

InbreedingCoeff

MappingQualityRankSumTest

QualByDepth

RMSMappingQuality

ReadPosRankSumTest

ReferenceBases

StrandBiasBySample

StrandOddsRatio

TandemRepeat

-AX
(same as for the -A option)

--output-mode
EMIT_VARIANTS_ONLY

EMIT_ALL_CONFIDENT_SITES

EMIT_ALL_ACTIVE_SITES

-max-reads-per-alignment-start
a positive integer

-min-dangling-branch-length
a positive integer

-min-pruning
a positive integer

-pcr-indel-model
NONE

HOSTILE

AGGRESSIVE

CONSERVATIVE

-standard-min-confidence-threshold-for-calling
a positive integer


## haplotypecaller Reference
Run HaplotypeCaller to convert BAM/CRAM to VCF.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑bam IN_BAM | Yes | Path to the input BAM/CRAM file for variant calling. The argument may also be a local folder containing several BAM files. |
| I/O | ‑‑in‑recal‑file IN_RECAL_FILE | No | Path to the input BQSR report. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to an interval file in one of these formats: Picard-style (.interval_list or .picard), GATK-style (.list or .intervals), or BED file (.bed). This option can be used multiple times. |
| I/O | ‑‑htvc‑bam‑output HTVC_BAM_OUTPUT | No | File to which assembled haplotypes should be written. If passing with --run-partition, multiple BAM files will be written. |
| I/O | ‑‑out‑variants OUT_VARIANTS | Yes | Path of the vcf/vcf.gz/g.vcf/gvcf.gz file after variant calling. |
| I/O | ‑‑htvc‑alleles HTVC_ALLELES | No | Path of the vcf.gz force-call file. The set of alleles to force-call regardless of evidence. |
| Tool | ‑‑haplotypecaller‑options HAPLOTYPECALLER_OPTIONS | No | Pass supported haplotype caller options as one string. The following are currently supported original haplotypecaller options: -A ,-AX ,--output-mode ,-max-reads-per-alignment-start , -min-dangling-branch-length , -min-pruning , -pcr-indel-model , -standard-min-confidence-threshold-for-calling , --activeregion-alt-multiplier (e.g. --haplotypecaller-options="-min-pruning 4 -standard-min-confidence-threshold-for-calling 30"). |
| Tool | ‑‑static‑quantized‑quals STATIC_QUANTIZED_QUALS | No | Use static quantized quality scores to a given number of levels. Repeat this option multiple times for multiple bins. |
| Tool | ‑‑gvcf | No | Generate variant calls in .gvcf format. |
| Tool | ‑‑disable‑read‑filter DISABLE_READ_FILTER | No | Disable the read filters for BAM entries. Currently, the supported read filters that can be disabled are MappingQualityAvailableReadFilter, MappingQualityReadFilter, NotSecondaryAlignmentReadFilter, and WellformedReadFilter. |
| Tool | ‑‑max‑alternate‑alleles MAX_ALTERNATE_ALLELES | No | Maximum number of alternate alleles to genotype. |
| Tool | ‑G ANNOTATION_GROUP, ‑‑annotation‑group ANNOTATION_GROUP | No | The groups of annotations to add to the output variant calls. Currently supported annotation groups are StandardAnnotation, StandardHCAnnotation, and AS_StandardAnnotation. |
| Tool | ‑GQB GVCF_GQ_BANDS, ‑‑gvcf‑gq‑bands GVCF_GQ_BANDS | No | Exclusive upper bounds for reference confidence GQ bands. Must be in the range [1, 100] and specified in increasing order. |
| Tool | ‑‑rna | No | Run haplotypecaller optimized for RNA data. |
| Tool | ‑‑dont‑use‑soft‑clipped‑bases | No | Don't use soft clipped bases for variant calling. |
| Tool | ‑‑minimum‑mapping‑quality MINIMUM_MAPPING_QUALITY | No | Minimum mapping quality to keep (inclusive). |
| Tool | ‑‑mapping‑quality‑threshold‑for‑genotyping MAPPING_QUALITY_THRESHOLD_FOR_GENOTYPING | No | Control the threshold for discounting reads from the genotyper due to mapping quality after the active region detection and assembly steps but before genotyping. |
| Tool | ‑‑enable‑dynamic‑read‑disqualification‑for‑genotyping | No | Will enable less strict read disqualification low base quality reads. |
| Tool | ‑‑min‑base‑quality‑score MIN_BASE_QUALITY_SCORE | No | Minimum base quality required to consider a base for calling. |
| Tool | ‑‑adaptive‑pruning | No | Use adaptive graph pruning algorithm when pruning De Bruijn graph. |
| Tool | ‑‑force‑call‑filtered‑alleles | No | Force-call filtered alleles included in the resource specified by --alleles. |
| Tool | ‑‑filter‑reads‑too‑long | No | Ignore all input BAM reads with size > 500bp. |
| Tool | ‑‑no‑alt‑contigs | No | Get rid of output records for alternate contigs. |
| Tool | ‑‑ploidy PLOIDY | No | Ploidy assumed for the BAM file. Currently only haploid (ploidy 1) and diploid (ploidy 2) are supported. (default: 2) |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to call the variants from the BAM/CRAM file. All intervals will have a padding of 100 to get read records, and overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Tool | ‑ip INTERVAL_PADDING, ‑‑interval‑padding INTERVAL_PADDING | No | Amount of padding (in base pairs) to add to each interval you are including. |
| Tool | ‑‑sample‑sex SAMPLE_SEX | No | Sex of the sample input. This option will override the sex determined from any X/Y read ratio range. Must be either male or female. |
| Tool | ‑‑range‑male RANGE_MALE | No | Inclusive male range for the X/Y read ratio. The sex is declared male if the actual ratio falls in the specified range. Syntax is "-" (e.g. "--range-male 1-10"). |
| Tool | ‑‑range‑female RANGE_FEMALE | No | Inclusive female range for the X/Y read ratio. The sex is declared female if the actual ratio falls in the specified range. Syntax is "-" (e.g. "--range-female 150-250"). |
| Tool | ‑‑use‑GRCh37‑regions | No | Use the pseudoautosomal regions for GRCh37 reference types. This flag should be used for GRCh37 and UCSC hg19 references. By default, GRCh38 regions are used. |
| Performance | ‑‑htvc‑low‑memory | No | Use low memory mode in htvc. |
| Performance | ‑‑num‑htvc‑threads NUM_HTVC_THREADS | No | Number of CPU threads per GPU to use. (default: 5) |
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



