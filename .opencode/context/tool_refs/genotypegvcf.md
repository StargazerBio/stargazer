# genotypegvcf

This tool converts variant calls in g.vcf format to VCF format.



This tool applies an accelerated GATK GenotypeGVCFs for joint genotyping, converting from g.vcf format to regular VCF format. This utilizes the HaplotypeCaller genotype likelihoods, produced with the -ERC GVCF flag, to joint genotype on one or more (multi-sample) g.vcf files.



See the genotypegvcf Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun genotypegvcf \
    --ref /workdir/${REFERENCE_FILE} \
    --in-gvcf /workdir/${INPUT_GVCF_FILE} \
    --out-vcf /outputdir/${OUTPUT_VCF}



### Compatible CPU GATK4 Command
$ gatk GenotypeGVCFs \
    -R <INPUT_DIR>/${REFERENCE_FILE} \
    -V <INPUT_DIR>/${INPUT_GVCF_FILE} \
    -O <OUTPUT_DIR>/${OUTPUT_VCF}



## genotypegvcf Reference
Convert GVCF to VCF.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑gvcf IN_GVCF | Yes | Input a g.vcf or g.vcf.gz file that will be converted to VCF. Required. |
| I/O | ‑‑out‑vcf OUT_VCF | Yes | Path to output VCF file. |
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

germline (GATK Germline Pipeline)
What is GATK?
GATK, the Genome Analysis Toolkit, is an industry standard software package developed by the Broad Institute of MIT and Harvard and designed to be used for a wide range of genomic analyses, including variant discovery, genotyping, and more. GATK is one of the most popular tools used in bioinformatics for analyzing next-generation sequencing datasets and is an industry standard for calling single nucleotide variants (SNVs) and insertions/deletions (InDels) from sequencing data in germline samples.



See the germline Reference section for a detailed listing of all available options.



Why GATK?
GATK offers robust, accurate analysis of sequencing data and is frequently updated to include the latest best practices for variant discovery. With high reliability and the ability to be used for a number of use cases, GATK is a gold standard tool for any researcher working with next-generation sequencing data.

How should I use GATK?
The GATK germline workflow for variant calling can be deployed within NVIDIA’s Parabricks software suite, which is designed for accelerated secondary analysis in genomics, bringing industry standard tools and workflows from CPU to GPU and delivering the same results at up to 60x faster runtimes. A 30x whole genome can be analyzed in under 25 minutes on an NVIDIA DGX system, compared to over 30 hours on a CPU instance (m5.24xlarge, 96 x vCPU), and exomes can be analyzed in just 4 minutes. This means Parabricks, running on one NVIDIA DGX A100, can analyze up to 25,000 whole genomes per year. The NVIDIA team collaborated with the GATK team at the Broad Institute to evaluate the accuracy of germline workflows. Through this rigorous process, they verified that the Parabricks workflows produce results that are functionally equivalent to the CPU-native GATK versions.

As a specific example, benchmarking on publicly available Genome in a Bottle (GIAB) samples with the fq2bam and germline caller workflows from the Parabricks suite produced variant calling results that were >0.9999 equivalent in both precision and recall to those produced by the BWA, MarkDuplicates, BQSR, and HaplotypeCaller commands in the GATK’s Whole Genome Germline Single Sample variant calling workflow.

Given one or more pairs of FASTQ files, you can run the germline variant tool to generate BAM, variants, duplicate metrics and recal.

The germline pipeline shown below resembles the GATK4 best practices pipeline. The inputs are BWA-indexed reference files, pair-ended FASTQ files, and knownSites for BQSR calculation. The outputs of this pipeline are as follows:

Aligned, co-ordinate sorted, duplicated marked BAM

BQSR report

Variants in vcf/g.vcf/g.vcf.gz format

germline.png


### Quick Start
Running the germline pipeline:

# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun germline \
    --ref /workdir/${REFERENCE_FILE} \
    --in-fq /workdir/${INPUT_FASTQ_1} /workdir/${INPUT_FASTQ_2} \
    --knownSites /workdir/${KNOWN_SITES_FILE} \
    --out-bam /outputdir/${OUTPUT_BAM} \
    --out-variants /outputdir/${OUTPUT_VCF} \
    --out-recal-file /outputdir/${OUT_RECAL_FILE}


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


### Compatible CPU-based BWA-MEM, GATK4 Commands
The commands below are the bwa-0.7.12 and GATK4 counterpart of the Parabricks command above. The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.

# Run bwa-mem and pipe output to create sorted BAM
$ bwa mem \
    -t 32 \
    -K 10000000 \
    -R '@RG\tID:sample_rg1\tLB:lib1\tPL:bar\tSM:sample\tPU:sample_rg1' \
    <INPUT_DIR>/${REFERENCE_FILE} <INPUT_DIR>/${INPUT_FASTQ_1} <INPUT_DIR>/${INPUT_FASTQ_2} | \
  gatk SortSam \
      --java-options -Xmx30g \
      --MAX_RECORDS_IN_RAM 5000000 \
      -I /dev/stdin \
      -O cpu.bam \
      --SORT_ORDER coordinate

# Mark Duplicates
$ gatk MarkDuplicates \
    --java-options -Xmx30g \
    -I cpu.bam \
    -O mark_dups_cpu.bam \
    -M metrics.txt

# Generate BQSR Report
$ gatk BaseRecalibrator \
    --java-options -Xmx30g \
    --input mark_dups_cpu.bam \
    --output <OUTPUT_DIR>/${OUT_RECAL_FILE} \
    --known-sites <INPUT_DIR>/${KNOWN_SITES_FILE} \
    --reference <INPUT_DIR>/${REFERENCE_FILE}

# Run ApplyBQSR Step
$ gatk ApplyBQSR \
    --java-options -Xmx30g \
    -R <INPUT_DIR>/${REFERENCE_FILE} \
    -I mark_dups_cpu.bam \
    --bqsr-recal-file <OUTPUT_DIR>/${OUT_RECAL_FILE} \
    -O cpu_nodups_BQSR.bam

#Run Haplotype Caller
$ gatk HaplotypeCaller \
    --java-options -Xmx30g \
    --input cpu_nodups_BQSR.bam \
    --output <OUTPUT_DIR>/${OUTPUT_VCF} \
    --reference <INPUT_DIR>/${REFERENCE_FILE} \
    --native-pair-hmm-threads 16



## germline Reference
Run Germline pipeline to convert FASTQ to VCF.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑fq [IN_FQ ...] | No | Path to the pair-ended FASTQ files followed by optional read groups with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:sampletPU:foo"). The files must be in fastq or fastq.gz format. All sets of inputs should have a read group; otherwise, none should have a read group, and it will be automatically added by the pipeline. This option can be repeated multiple times. Example 1: --in-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz --in-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz. Example 2: --in-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz "@RGtID:footLB:lib1tPL:bartSM:sampletPU:unit1" --in-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz "@RGtID:foo2tLB:lib1tPL:bartSM:sampletPU:unit2". For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑in‑se‑fq [IN_SE_FQ ...] | No | Path to the single-ended FASTQ file followed by optional read group with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:sampletPU:foo"). The file must be in fastq or fastq.gz format. Either all sets of inputs have a read group, or none should have one, and it will be automatically added by the pipeline. This option can be repeated multiple times. Example 1: --in-se-fq sampleX_1.fastq.gz --in-se-fq sampleX_2.fastq.gz . Example 2: --in-se-fq sampleX_1.fastq.gz "@RGtID:footLB:lib1tPL:bartSM:sampletPU:unit1" --in-se-fq sampleX_2.fastq.gz "@RGtID:foo2tLB:lib1tPL:bartSM:sampletPU:unit2" . For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑knownSites KNOWNSITES | No | Path to a known indels file. The file must be in vcf.gz format. This option can be used multiple times. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to an interval file in one of these formats: Picard-style (.interval_list or .picard), GATK-style (.list or .intervals), or BED file (.bed). This option can be used multiple times. |
| I/O | ‑‑out‑recal‑file OUT_RECAL_FILE | No | Path of the report file after Base Quality Score Recalibration. |
| I/O | ‑‑out‑bam OUT_BAM | Yes | Path of BAM file after marking duplicates. |
| I/O | ‑‑htvc‑bam‑output HTVC_BAM_OUTPUT | No | File to which assembled haplotypes should be written in HaplotypeCaller. If passing with --run-partition, multiple BAM files will be written. |
| I/O | ‑‑out‑variants OUT_VARIANTS | Yes | Path of the vcf/vcf.gz/gvcf/gvcf.gz file after variant calling. |
| I/O | ‑‑out‑duplicate‑metrics OUT_DUPLICATE_METRICS | No | Path of duplicate metrics file after marking duplicates. |
| I/O | ‑‑htvc‑alleles HTVC_ALLELES | No | Path of the vcf.gz force-call file. The set of alleles to force-call regardless of evidence. |
| Tool | ‑‑max‑read‑length MAX_READ_LENGTH | No | Maximum read length/size (i.e., sequence length) used for bwa and filtering FASTQ input. (default: 480) |
| Tool | ‑‑min‑read‑length MIN_READ_LENGTH | No | Minimum read length/size (i.e., sequence length) used for bwa and filtering FASTQ input. (default: 1) |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to call bqsr from the input reads. All intervals will have a padding of 100 to get read records, and overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Tool | ‑‑bwa‑options BWA_OPTIONS | No | Pass supported bwa mem options as one string. The current original bwa mem supported options are: -M, -Y, -C, -T, -B, -U, -L, and -K (e.g. --bwa-options="-M -Y"). |
| Tool | ‑‑no‑warnings | No | Suppress warning messages about system thread and memory usage. |
| Tool | ‑‑filter‑flag FILTER_FLAG | No | Don't generate SAM entries in the output if the entry's flag's meet this criteria. Criteria: (flag & filter != 0). (default: 0) |
| Tool | ‑‑skip‑multiple‑hits | No | Filter SAM entries whose length of SA is not 0. |
| Tool | ‑‑align‑only | No | Generate output BAM after bwa-mem. The output will not be co-ordinate sorted or duplicates will not be marked. |
| Tool | ‑‑no‑markdups | No | Do not perform the Mark Duplicates step. Return BAM after sorting. |
| Tool | ‑‑markdups‑single‑ended‑start‑end | No | Mark duplicate on single-ended reads by 5' and 3' end. |
| Tool | ‑‑fix‑mate | No | Add mate cigar (MC) and mate quality (MQ) tags to the output file. |
| Tool | ‑‑markdups‑assume‑sortorder‑queryname | No | Assume the reads are sorted by queryname for marking duplicates. This will mark secondary, supplementary, and unmapped reads as duplicates as well. This flag will not impact variant calling while increasing processing times. |
| Tool | ‑‑markdups‑picard‑version‑2182 | No | Assume marking duplicates to be similar to Picard version 2.18.2. |
| Tool | ‑‑monitor‑usage | No | Monitor approximate CPU utilization and host memory usage during execution. |
| Tool | ‑‑optical‑duplicate‑pixel‑distance OPTICAL_DUPLICATE_PIXEL_DISTANCE | No | The maximum offset between two duplicate clusters in order to consider them optical duplicates. Ignored if --out-duplicate-metrics is not passed. |
| Tool | ‑‑read‑group‑sm READ_GROUP_SM | No | SM tag for read groups in this run. |
| Tool | ‑‑read‑group‑lb READ_GROUP_LB | No | LB tag for read groups in this run. |
| Tool | ‑‑read‑group‑pl READ_GROUP_PL | No | PL tag for read groups in this run. |
| Tool | ‑‑read‑group‑id‑prefix READ_GROUP_ID_PREFIX | No | Prefix for the ID and PU tags for read groups in this run. This prefix will be used for all pairs of FASTQ files in this run. The ID and PU tags will consist of this prefix and an identifier, that will be unique for a pair of FASTQ files. |
| Tool | ‑ip INTERVAL_PADDING, ‑‑interval‑padding INTERVAL_PADDING | No | Amount of padding (in base pairs) to add to each interval you are including. |
| Tool | ‑‑standalone‑bqsr | No | Run standalone BQSR. |
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
| Tool | ‑‑sample‑sex SAMPLE_SEX | No | Sex of the sample input. This option will override the sex determined from any X/Y read ratio range. Must be either male or female. |
| Tool | ‑‑range‑male RANGE_MALE | No | Inclusive male range for the X/Y read ratio. The sex is declared male if the actual ratio falls in the specified range. Syntax is "-" (e.g. "--range-male 1-10"). |
| Tool | ‑‑range‑female RANGE_FEMALE | No | Inclusive female range for the X/Y read ratio. The sex is declared female if the actual ratio falls in the specified range. Syntax is "-" (e.g. "--range-female 150-250"). |
| Tool | ‑‑use‑GRCh37‑regions | No | Use the pseudoautosomal regions for GRCh37 reference types. This flag should be used for GRCh37 and UCSC hg19 references. By default, GRCh38 regions are used. |
| Performance | ‑‑bwa‑nstreams BWA_NSTREAMS | No | Number of streams per GPU to use; note: more streams increases device memory usage. Default is auto which will try to use an optimal amount of device memory. (default: auto) |
| Performance | ‑‑bwa‑cpu‑thread‑pool BWA_CPU_THREAD_POOL | No | Number of threads to devote to CPU thread pool per GPU. (default: 16) |
| Performance | ‑‑num‑cpu‑threads‑per‑stage NUM_CPU_THREADS_PER_STAGE | No | (Same as above) Number of threads to devote to CPU thread pool per GPU. |
| Performance | ‑‑bwa‑normalized‑queue‑capacity BWA_NORMALIZED_QUEUE_CAPACITY | No | Normalized capacity for alignment work queues, use a lower value if CPU memory is low; final value will be * . (default: 10) |
| Performance | ‑‑bwa‑primary‑cpus BWA_PRIMARY_CPUS | No | Number of primary CPU threads driving its associated thread pool. Default is auto which will use 1 primary thread with its associated thread pool per GPU. (default: auto) |
| Performance | ‑‑gpuwrite | No | Use one GPU to accelerate writing final BAM/CRAM. |
| Performance | ‑‑gpuwrite‑deflate‑algo GPUWRITE_DEFLATE_ALGO | No | Choose the nvCOMP DEFLATE algorithm to use with --gpuwrite. Note these options do not correspond to CPU DEFLATE options. Valid options are 1, 2, and 4. Option 1 is fastest, while options 2 and 4 have progressively lower throughput but higher compression ratios. The default value is 1 when the user does not provide an input (i.e., None). |
| Performance | ‑‑gpusort | No | Use GPUs to accelerate sorting and marking. |
| Performance | ‑‑use‑gds | No | Use GPUDirect Storage (GDS) to enable a direct data path for direct memory access (DMA) transfers between GPU memory and storage. Must be used concurrently with --gpuwrite. Please refer to Parabricks Documentation > Best Performance for information on how to set up and use GPUDirect Storage. |
| Performance | ‑‑memory‑limit MEMORY_LIMIT | No | System memory limit in GBs during sorting and postsorting. By default, the limit is half of the total system memory. (default: 62) |
| Performance | ‑‑low‑memory | No | Use low memory mode; will lower the number of streams per GPU. |
| Performance | ‑‑htvc‑low‑memory | No | Use low memory mode in htvc. |
| Performance | ‑‑num‑htvc‑threads NUM_HTVC_THREADS | No | Number of CPU threads per GPU to use. (default: 5) |
| Performance | ‑‑run‑partition | No | Divide the whole genome into multiple partitions and run multiple processes at the same time, each on one partition. |
| Performance | ‑‑gpu‑num‑per‑partition GPU_NUM_PER_PARTITION | No | Number of GPUs to use per partition. |
| Performance | ‑‑read‑from‑tmp‑dir | No | Running variant caller reading from bin files generated by Aligner and sort. Run postsort in parallel. This option will increase device memory usage. |
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

Note
The --in-fq option takes the names of two FASTQ files, optionally followed by a quoted read group. The FASTQ filenames must not start with a hyphen.

Note
In the values provided to --haplotypecaller-options --output-mode requires two leading hyphens, while all other values take a single hyphen.

giraffe (vg giraffe + GATK)
Beta
Note that the Parabricks GPU-accelerated Giraffe tool is currently in beta.


Generate BAM output given one or a pair of FASTQ files using the pangenome aligner VG Giraffe [1] [2].



See the giraffe Reference section for a detailed listing of all available options.


What is giraffe?
VG Giraffe is a short-read mapping tool developed by Dr. Benedict Paten's lab at the University of California, Santa Cruz (UCSC). This innovative tool can align reads to a graph representation of multiple reference genomes, enhancing the quality of downstream analyses. By accurately mapping reads to thousands of genomes simultaneously, VG Giraffe offers a substantial improvement over traditional single-reference aligners.

Why giraffe?
By utilizing a graph-based approach, VG Giraffe can more effectively handle genetic diversity and structural variations across populations. Here are three key benefits of using VG Giraffe:

Improved accuracy: VG Giraffe achieves higher precision and recall in read mapping compared to linear genome aligners, especially when dealing with complex genomic regions or populations with significant genetic diversity.

Reduced reference bias (or mapping bias): By incorporating multiple haplotypes and known variants into its graph structure, VG Giraffe minimizes the reference bias inherent in traditional linear genome aligners. This leads to more comprehensive and unbiased characterization of genetic variation, especially for samples that diverge significantly from the standard reference genome.

Faster performance: Despite working with more complex graph structures, VG Giraffe is significantly faster than its predecessor VG Map and comparable in speed to popular linear genome mappers. It can map sequencing reads to thousands of human genomes at a speed similar to methods that map to a single reference genome.

How should I use giraffe in Parabricks?
VG Giraffe can be used within Parabricks, a software suite designed for accelerated secondary analysis in genomics. Our wrapper (pbrun giraffe) will run our GPU-accelerated VG Giraffe and sort the output BAM by coordinate.

While users can build custom reference graphs for VG Giraffe using the VG Autoindex tool, pre-built pangenome graphs are also available. Dr. Paten's lab and the Human Pangenome Consortium have made these resources publicly accessible, allowing researchers to leverage high-quality, ready-to-use pangenome graphs for their analyses (HPRC data).

Starting from Parabricks version 4.5.1, only index files .gbz, .min, and .dist, are required to run Giraffe.

The set of index files used in the test below can be downloaded using the wget as follows:

# Donwload index files
echo -e "dist\nmin\ngbz\nhapl" | xargs -I {} \
    wget "https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.{}"

# Extract the list of paths corresponding to GRCh38
docker run --rm --volume $(pwd):/workdir \
    --workdir /workdir \
    quay.io/vgteam/vg:v1.59.0 \
    vg paths -x hprc-v1.1-mc-grch38.gbz -L -Q GRCh38 > hprc-v1.1-mc-grch38.paths

# Filter paths list
grep -v _decoy hprc-v1.1-mc-grch38.paths \
    | grep -v _random \
    | grep -v chrUn_ \
    | grep -v chrEBV \
    | grep -v chrM \
    | grep -v chain_ > hprc-v1.1-mc-grch38.paths.sub



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun giraffe --read-group "sample_rg1" \
    --sample "sample-name" --read-group-library "library" \
    --read-group-platform "platform" --read-group-pu "pu" \
    --dist-name /workdir/hprc-v1.1-mc-grch38.dist \
    --minimizer-name /workdir/hprc-v1.1-mc-grch38.min \
    --gbz-name /workdir/hprc-v1.1-mc-grch38.gbz \
    --ref-paths /workdir/hprc-v1.1-mc-grch38.paths.sub \
    --in-fq /workdir/${INPUT_FASTQ_1} /workdir/${INPUT_FASTQ_2} \
    --out-bam /outputdir/${OUTPUT_BAM}


System Requirements and Useful Options for Performance
To ensure optimal performance with VG Giraffe, please consider the following system requirements based on your GPU configuration:

A 2 GPU system should have at least 100GB CPU RAM and at least 32 CPU threads.

A 4 GPU system should have at least 200GB CPU RAM and at least 64 CPU threads.

During runtime, VG Giraffe loads index data into GPU device memory, which can impact available memory for concurrent operations. To optimize device memory usage and performance, consider the following options tailored to your GPU device memory capacity:

For 16GB devices (e.g. T4): Use --low-memory option

For 16GB-40GB devices (e.g. L4, A10) optimize performance by adjusting:

--nstreams: Controls the number of CUDA streams per GPU

--batch-size: Adjusts the number of reads processed in a batch

For L4 best performance was obtained using --nstreams 2 --batch-size 5000

For >40GB devices: Default parameters are sufficient; however, there is the potential for further optimization by adjusting the aforementioned parameters.

For >80GB devices, better performance can be achieved by increasing the number of streams and by enabling the computation of minimizers and seeds on GPU: --minimizers-gpu. Additionally, a performance improvement can be obtained by setting --minimizers-gpu-sort. Note that while --minimizers-gpu will produce the same BAM file as baseline Giraffe, --minimizers-gpu-sort will produce a BAM file that differs from baseline. This is because baseline Giraffe sorts minimizers using a non-stable sort, whereas the GPU implementation uses a stable sort.

Note: While a fixed base memory allocation exists per device, the number of streams and batch size are the primary factors affecting total device memory consumption.

Using Giraffe in Variant Calling Workflows
To use Giraffe-aligned BAM files for variant calling, you need to extract the appropriate reference file from the Giraffe index files. Run the following commands from the directory containing the Giraffe index files:

# Extract the sequences corrresponding to the list of paths to a FASTA file
docker run --rm --volume $(pwd):/workdir \
    --workdir /workdir \
    quay.io/vgteam/vg:v1.59.0 \
    vg paths -x hprc-v1.1-mc-grch38.gbz -p hprc-v1.1-mc-grch38.paths.sub -F > hprc-v1.1-mc-grch38.fa

# Index the fasta file
samtools faidx hprc-v1.1-mc-grch38.fa


These commands will generate a FASTA file (hprc-v1.1-mc-grch38.fa), and the corresponding index (hprc-v1.1-mc-grch38.fa.fai), that can be used as the reference for variant calling. Note that these files can be also used for BQSR (bqsr). We can now run Giraffe to obtain the aligned BAM as follows:

# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun giraffe --read-group "sample_rg1" \
    --sample "sample-name" --read-group-library "library" \
    --read-group-platform "platform" --read-group-pu "pu" \
    --dist-name /workdir/hprc-v1.1-mc-grch38.dist \
    --minimizer-name /workdir/hprc-v1.1-mc-grch38.min \
    --gbz-name /workdir/hprc-v1.1-mc-grch38.gbz \
    --ref-paths /workdir/hprc-v1.1-mc-grch38.paths.sub \
    --in-fq /workdir/${INPUT_FASTQ_1} /workdir/${INPUT_FASTQ_2} \
    --out-bam /outputdir/${OUTPUT_BAM}


Once you have the Giraffe-aligned BAM file and the extracted reference FASTA, you can proceed with variant calling using HaplotypeCaller, Deepvariant or Pangenome_aware_deepvariant.

# Haplotype Caller
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun haplotypecaller \
    --ref /workdir/hprc-v1.1-mc-grch38.fa \
    --in-bam /workdir/${INPUT_BAM} \
    --in-recal-file /workdir/${INPUT_RECAL_FILE} \
    --out-variants /outputdir/${OUTPUT_VCF}

# Deepvariant
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun deepvariant \
    --ref /workdir/hprc-v1.1-mc-grch38.fa \
    --in-bam /workdir/${INPUT_BAM} \
    --out-variants /outputdir/${OUTPUT_VCF}

# Pangenome_aware_deepvariant
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun pangenome_aware_deepvariant \
    --ref /workdir/hprc-v1.1-mc-grch38.fa \
    --pangenome /workdir/hprc-v1.1-mc-grch38.gbz \
    --in-bam /workdir/${INPUT_BAM} \
    --out-variants /outputdir/${OUTPUT_VCF}


For more detailed instructions on variant calling, please refer to the tool-specific documentation (haplotypecaller, deepvariant, pangenome_aware_deepvariant).

Using Giraffe with Haplotype Sampling
Giraffe's haplotype sampling functionality, activated using arguments --haplotype-name and --kff-name, was introduced to significantly enhance alignment accuracy by tailoring the reference graph to the specific genetic profile of a sample. This process begins by analyzing sequencing reads with a kmer counter to identify patterns of kmer presence and frequency. Using this information, Giraffe sub-samples the GBWT (using the original .hapl and .gbz files) to select haplotypes that best represent the sample, creating a customized graph. From this tailored graph, Giraffe also generates new index files (.dist and .min) that are optimized for the sample to be analyzed.

These steps can be performed using the baseline VG container for graph customization and index generation, followed by Parabricks' accelerated Giraffe for high-performance alignment, as demonstrated below:


| Type | Name | Required? | Description |
|------|------|-----------|-------------|

    quay.io/biocontainers/kmc:3.2.4--haf24da9_3 \
    kmc \
        -k29 \
        -m128 \
        -okff \
        -t64 \
        @input.fq.paths \
        input.fq.distr kmc_tmp_dir


# Compute the sampled .gbz file using the baseline container
docker run --rm --volume $(pwd):/workdir \
    --workdir /workdir \
    quay.io/vgteam/vg:v1.59.0 \
    vg haplotypes \
        -v 2 -t 64 \
        --include-reference \
        --diploid-sampling \
        -i hprc-v1.1-mc-grch38.hapl \
        -k input.fq.distr.kff \
        -g hprc-v1.1-mc-grch38.sampled.gbz \
        hprc-v1.1-mc-grch38.gbz

# Obtain the sampled .dist file using the baseline container
docker run --rm --volume $(pwd):/workdir \
    --workdir /workdir \
    quay.io/vgteam/vg:v1.59.0 \
    vg index \
        -t 64 \
        -j hprc-v1.1-mc-grch38.sampled.dist \
        hprc-v1.1-mc-grch38.sampled.gbz

# Obtain the sampled .min file using the baseline container
docker run --rm --volume $(pwd):/workdir \
    --workdir /workdir \
    quay.io/vgteam/vg:v1.59.0 \
    vg minimizer \
        -p \
        -t 64 \
        -d hprc-v1.1-mc-grch38.sampled.dist \
        -o hprc-v1.1-mc-grch38.sampled.min \
        hprc-v1.1-mc-grch38.sampled.gbz

# Align the reads to the sampled graph using Parabricks Giraffe
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun giraffe --read-group "sample_rg1" \
    --sample "sample-name" --read-group-library "library" \
    --read-group-platform "platform" --read-group-pu "pu" \
    --dist-name hprc-v1.1-mc-grch38.sampled.dist \
    --minimizer-name hprc-v1.1-mc-grch38.sampled.min \
    --gbz-name hprc-v1.1-mc-grch38.sampled.gbz \
    --ref-paths hprc-v1.1-mc-grch38.paths.sub \
    --in-fq ${INPUT_FASTQ_1} ${INPUT_FASTQ_2} \
    --out-bam /outputdir/${OUTPUT_BAM}



### Compatible CPU-based vg giraffe and GATK4 Commands
The commands below are the vg-1.59.0 and GATK4 counterpart of the Parabricks command above. The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.

# Run giraffe and pipe the output to create a sorted BAM.
$ vg giraffe \
    -t 16 \
    -d /workdir/hprc-v1.1-mc-grch38.dist \
    -m /workdir/hprc-v1.1-mc-grch381.min \
    -Z /workdir/hprc-v1.1-mc-grch38.gbz \
    --ref-paths /workdir/hprc-v1.1-mc-grch38.paths.sub \
    -f /workdir/${INPUT_FASTQ_1} \
    -f /workdir/${INPUT_FASTQ_2} \
    --output-format bam | \
  gatk SortSam \
    --java-options -Xmx30g \
    --MAX_RECORDS_IN_RAM 5000000 \
    -I /dev/stdin \
    -O cpu.bam \
    --SORT_ORDER coordinate

# Mark duplicates.
$ gatk MarkDuplicates \
    -I cpu.bam \
    -O cpu.markdup.bam \
    -M metrics.txt


Source of Mismatches
When comparing output with the CPU counterpart the following can be sources of small differences.

Baseline VG Container

When comparing output between baseline giraffe and Parabricks' accelerated version, if you intend to use the baseline vg container (quay.io/vgteam/vg:v1.59.0), you will need to re-build the container with an Ubuntu 22.04 base. This is because of changes in the C++ standard library for the default gcc version of the underlying OS (#4391). Modify line 6 of their Dockerfile to reference mirror.gcr.io/library/ubuntu:22.04 instead of 20.04. Rebuild a container with the following command.

git clone https://github.com/vgteam/vg.git
cd vg
git checkout v1.59.0
git submodule update --init --recursive
make version
docker build --no-cache -f Dockerfile --build-arg THREADS=16 --tag \
  <YOUR_CONTIANER_NAME> --network host ./


Unmapped reads

Parabricks giraffe sorts unmapped reads slightly differently than baseline GATK SortSam. Unmapped reads can be filtered with samtools by running samtools view -F 4.


## giraffe Reference
Align reads to a pangenome graph.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑in‑fq [IN_FQ ...] | No | Path to the paired-end FASTQ files. The files must be in fastq or fastq.gz format. Example 1: --in-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz. |
| I/O | ‑‑in‑fq‑list IN_FQ_LIST | No | Path to a file that contains the locations of pair-ended FASTQ files. Each line must contain the location of the FASTQ files followed by a read group, each separated by a space. Each pair of files (and associated read group) must be on a separate line. Files must be in fastq/fastq.gz format. Line syntax: . |
| I/O | ‑‑in‑se‑fq [IN_SE_FQ ...] | No | Path to the single-end FASTQ file. The file must be in fastq or fastq.gz format. |
| I/O | ‑‑in‑se‑fq‑list IN_SE_FQ_LIST | No | Path to a file that contains the locations of single-ended FASTQ files. Each line must contain the location of the FASTQ files followed by a read group, each separated by a space. Each file (and associated read group) must be on a separate line. Files must be in fastq/fastq.gz format. Line syntax: . |
| I/O | ‑d DIST_NAME, ‑‑dist‑name DIST_NAME | Yes | Cluster using this distance index. |
| I/O | ‑m MINIMIZER_NAME, ‑‑minimizer‑name MINIMIZER_NAME | Yes | Use this minimizer index. |
| I/O | ‑Z GBZ_NAME, ‑‑gbz‑name GBZ_NAME | Yes | Map to this GBZ graph. |
| I/O | ‑x XG_NAME, ‑‑xg‑name XG_NAME | No | XG graph used for BAM output. |
| I/O | ‑g GRAPH_NAME, ‑‑graph‑name GRAPH_NAME | No | GBWTGraph used for mapping. |
| I/O | ‑H GBWT_NAME, ‑‑gbwt‑name GBWT_NAME | No | GBWT index for mapping. |
| I/O | ‑‑out‑bam OUT_BAM | Yes | Path of a BAM file for output. |
| I/O | ‑‑ref‑paths REF_PATHS | No | Path to file containing ordered list of paths in the graph, one per line or HTSlib .dict, for HTSLib @SQ headers. |
| I/O | ‑‑out‑duplicate‑metrics OUT_DUPLICATE_METRICS | No | Path of duplicate metrics file after marking duplicates. |
| Tool | ‑‑read‑group READ_GROUP | No | Read group ID for this run. |
| Tool | ‑‑sample SAMPLE | No | Sample (SM) tag for read group in this run. |
| Tool | ‑‑read‑group‑library READ_GROUP_LIBRARY | No | Library (LB) tag for read group in this run. |
| Tool | ‑‑read‑group‑platform READ_GROUP_PLATFORM | No | Platform (PL) tag for read group in this run; refers to platform/technology used to produce reads. |
| Tool | ‑‑read‑group‑pu READ_GROUP_PU | No | Platform unit (PU) tag for read group in this run. |
| Tool | ‑‑prune‑low‑cplx | No | Prune short and low complexity anchors during linear format realignment. |
| Tool | ‑‑max‑fragment‑length MAX_FRAGMENT_LENGTH | No | Assume that fragment lengths should be smaller than MAX-FRAGMENT-LENGTH when estimating the fragment length distribution. |
| Tool | ‑‑fragment‑mean FRAGMENT_MEAN | No | Force the fragment length distribution to have this mean. |
| Tool | ‑‑fragment‑stdev FRAGMENT_STDEV | No | Force the fragment length distribution to have this standard deviation. |
| Tool | ‑‑align‑only | No | Generate output BAM after vg-giraffe alignment. The output will not be co-ordinate sorted. |
| Tool | ‑‑copy‑comment | No | Append FASTQ comment to BAM output via auxiliary tag. |
| Tool | ‑‑no‑markdups | No | Do not perform the Mark Duplicates step. Return BAM after sorting. |
| Tool | ‑‑markdups‑single‑ended‑start‑end | No | Mark duplicate on single-ended reads by 5' and 3' end. |
| Tool | ‑‑markdups‑assume‑sortorder‑queryname | No | Assume the reads are sorted by queryname for marking duplicates. This will mark secondary, supplementary, and unmapped reads as duplicates as well. This flag will not impact variant calling while increasing processing times. |
| Tool | ‑‑markdups‑picard‑version‑2182 | No | Assume marking duplicates to be similar to Picard version 2.18.2. |
| Tool | ‑‑optical‑duplicate‑pixel‑distance OPTICAL_DUPLICATE_PIXEL_DISTANCE | No | The maximum offset between two duplicate clusters in order to consider them optical duplicates. Ignored if --out-duplicate-metrics is not passed. |
| Tool | ‑‑monitor‑usage | No | Monitor approximate CPU utilization and host memory usage during execution. |
| Tool | ‑‑max‑read‑length MAX_READ_LENGTH | No | Maximum read length/size (i.e., sequence length) used for giraffe and filtering FASTQ input. (default: 480) |
| Tool | ‑‑min‑read‑length MIN_READ_LENGTH | No | Minimum read length/size (i.e., sequence length) used for giraffe and filtering FASTQ input. (default: 1) |
| Performance | ‑‑minimizers‑gpu | No | Uses GPU to compute minimizers and seeds. |
| Performance | ‑‑minimizers‑gpu‑sort | No | Uses GPU to sort minimizers. |
| Performance | ‑‑nstreams NSTREAMS | No | Number of streams per GPU to use; note: more streams increases device memory usage. (default: 3) |
| Performance | ‑‑num‑cpu‑threads‑per‑gpu NUM_CPU_THREADS_PER_GPU | No | Number of primary CPU threads to use per GPU. (default: 16) |
| Performance | ‑‑batch‑size BATCH_SIZE | No | Batch size used for processing alignments. (default: 10000) |
| Performance | ‑‑write‑threads WRITE_THREADS | No | Number of threads used for writing and pre-sorting output. (default: 4) |
| Performance | ‑‑gpuwrite | No | Use one GPU to accelerate writing final BAM/CRAM. |
| Performance | ‑‑gpuwrite‑deflate‑algo GPUWRITE_DEFLATE_ALGO | No | Choose the nvCOMP DEFLATE algorithm to use with --gpuwrite. Note these options do not correspond to CPU DEFLATE options. Valid options are 1, 2, and 4. Option 1 is fastest, while options 2 and 4 have progressively lower throughput but higher compression ratios. The default value is 1 when the user does not provide an input (i.e., None). |
| Performance | ‑‑gpusort | No | Use GPUs to accelerate sorting and marking. |
| Performance | ‑‑use‑gds | No | Use GPUDirect Storage (GDS) to enable a direct data path for direct memory access (DMA) transfers between GPU memory and storage. Must be used concurrently with --gpuwrite. Please refer to Parabricks Documentation > Best Performance for information on how to set up and use GPUDirect Storage. |
| Performance | ‑‑memory‑limit MEMORY_LIMIT | No | System memory limit in GBs during sorting and postsorting. By default, the limit is half of the total system memory. (default: 62) |
| Performance | ‑‑low‑memory | No | Use low memory mode; will lower the number of streams per GPU and decrease the batch size. |
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



