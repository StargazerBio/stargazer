# pacbio_germline

Run the germline variant tool to generate BAM and variants on long read sequences using minimap2 for alignment as well as the DeepVariant variant caller.



See the pacbio_germline Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun pacbio_germline \
    --ref /workdir/${REFERENCE_FILE} \
    --in-fq /workdir/${INPUT_FASTQ} \
    --out-bam /outputdir/${OUTPUT_BAM} \
    --out-variants /outputdir/${OUTPUT_VCF}



### Compatible CPU-based minimap2, GATK4, and Google DeepVariant Commands
The commands below are the minimap2-v2.26, GATK4, and Google DeepVariant counterpart of the Clara Parabricks command above. The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.


# Run minimap2 and pipe the output to create a sorted BAM.
$ minimap2 -ax map-pbmm2 \
    <INPUT_DIR>/${REFERENCE_FILE} \
    <INPUT_DIR>/${INPUT_FASTQ} | \
  gatk SortSam \
    --java-options -Xmx30g \
    --MAX_RECORDS_IN_RAM 5000000 \
    -I /dev/stdin \
    -O cpu.bam \
    --SORT_ORDER coordinate

 # Run deepvariant
BIN_VERSION="1.9.0"
sudo docker run \
  -v "${PWD}":"/input" \
  -v "${PWD}/output":"/output" \
  -v "${PWD}/Ref":"/reference" \
  google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type PACBIO \
  --ref /reference/${REFERENCE_FILE} \
  --reads cpu.bam \
  --output_vcf /output/"${OUTPUT_VCF_FILE}" \
  --num_shards $(nproc) \
  --disable_small_model=true \
  --make_examples_extra_args "ws_use_window_selector_model=true"



Please note that two changes must be made to the baseline minimap2 code in order to match the results exactly:



Firstly, a new preset must be made in options.c in the mm_set_opt function that tries to replicate the preset of pbmm2 by setting these parameters as a new preset named "map-pbmm2":


io->k = 19;
io->w = 19;
io->batch_size = 0x7fffffffffffffffL; // always build a uni-part index
mo->flag |= MM_F_CIGAR;
mo->flag |= MM_F_SOFTCLIP;
mo->flag |= MM_F_LONG_CIGAR;
mo->flag |= MM_F_EQX;
mo->flag |= MM_F_NO_PRINT_2ND; // Allow secondaries with enforced mapping, but disable per default!
mo->zdrop = 400;
mo->zdrop_inv = 50;
mo->a = 1;
mo->b = 4;
mo->q = 6;
mo->q2 = 26;
mo->e = 2;
mo->e2 = 1;
mo->bw = 2000;
mo->max_gap = 10000;
mo->occ_dist = 500;
mo->min_mid_occ = 50;
mo->max_mid_occ = 500;
mo->min_dp_max = 500;



Secondly, a fix must be made to the baseline KSW2 code to round the loop fission start and end points by changing them to st and en respectively. If the start point (st0) is a number below 16, but greater than 0, its scoring values will not be initialized correctly, but will still be used later when computing the actual alignment. This can be fixed by rounding the start and end points to multiples of 16.



To make this fix, change the following code in ksw2_extd2_sse.c:


        // loop fission: set scores first
        if (!(flag & KSW_EZ_GENERIC_SC)) {
            for (t = st0; t <= en0; t += 16) {
                __m128i sq, st, tmp, mask;
                sq = _mm_loadu_si128((__m128i*)&sf[t]);
                st = _mm_loadu_si128((__m128i*)&qrr[t]);
                mask = _mm_or_si128(_mm_cmpeq_epi8(sq, m1_), _mm_cmpeq_epi8(st, m1_));
                tmp = _mm_cmpeq_epi8(sq, st);
#ifdef __SSE4_1__
                tmp = _mm_blendv_epi8(sc_mis_, sc_mch_, tmp);
                tmp = _mm_blendv_epi8(tmp,     sc_N_,   mask);
#else
                tmp = _mm_or_si128(_mm_andnot_si128(tmp,  sc_mis_), _mm_and_si128(tmp,  sc_mch_));
                tmp = _mm_or_si128(_mm_andnot_si128(mask, tmp),     _mm_and_si128(mask, sc_N_));
#endif
                _mm_storeu_si128((__m128i*)((int8_t*)s + t), tmp);
            }
        } else {
            for (t = st0; t <= en0; ++t)
                ((uint8_t*)s)[t] = mat[sf[t] * m + qrr[t]];
        }



Fixed version that uses lf_start and lf_en:

        // loop fission: set scores first
        int lf_start = st, lf_en = en;
        if (!(flag & KSW_EZ_GENERIC_SC)) {
            for (t = lf_start; t <= lf_en; t += 16) {
                __m128i sq, st, tmp, mask;
                sq = _mm_loadu_si128((__m128i*)&sf[t]);
                st = _mm_loadu_si128((__m128i*)&qrr[t]);
                mask = _mm_or_si128(_mm_cmpeq_epi8(sq, m1_), _mm_cmpeq_epi8(st, m1_));
                tmp = _mm_cmpeq_epi8(sq, st);
#ifdef __SSE4_1__
                tmp = _mm_blendv_epi8(sc_mis_, sc_mch_, tmp);
                tmp = _mm_blendv_epi8(tmp,     sc_N_,   mask);
#else
                tmp = _mm_or_si128(_mm_andnot_si128(tmp,  sc_mis_), _mm_and_si128(tmp,  sc_mch_));
                tmp = _mm_or_si128(_mm_andnot_si128(mask, tmp),     _mm_and_si128(mask, sc_N_));
#endif
                _mm_storeu_si128((__m128i*)((int8_t*)s + t), tmp);
            }
        } else {
            for (t = lf_start; t <= lf_en; ++t)
                ((uint8_t*)s)[t] = mat[sf[t] * m + qrr[t]];
        }


Models for additional GPUs
See the DeepVariant Models for additional GPUs section for instructions on downloading and using model files for additional GPUs.


## pacbio_germline Reference
Run the germline pipeline from FASTQ/BAM to VCF by aligning long read sequences with minimap2 and using a deep neural network analysis.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑index INDEX | No | Path to a minimizer index file generated by vanilla minimap2 to reduce indexing time. |
| I/O | ‑‑in‑fq IN_FQ | No | Path to a query sequence file in fastq or fastq.gz format. |
| I/O | ‑‑in‑bam IN_BAM | No | Path to the input BAM/CRAM file. |
| I/O | ‑‑knownSites KNOWNSITES | No | Path to a known indels file. The file must be in vcf.gz format. This option can be used multiple times. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to an interval file in one of these formats: Picard-style (.interval_list or .picard), GATK-style (.list or .intervals), or BED file (.bed). This option can be used multiple times. |
| I/O | ‑‑pb‑model‑file PB_MODEL_FILE | No | Path to a non-default parabricks model file for deepvariant. |
| I/O | ‑‑out‑recal‑file OUT_RECAL_FILE | No | Path of the report file after Base Quality Score Recalibration. |
| I/O | ‑‑out‑bam OUT_BAM | Yes | Path of BAM file after marking duplicates. |
| I/O | ‑‑out‑variants OUT_VARIANTS | Yes | Path of the vcf/vcf.gz/gvcf/gvcf.gz file after variant calling. |
| I/O | ‑‑out‑duplicate‑metrics OUT_DUPLICATE_METRICS | No | Path of a duplicate metrics file after marking duplicates. |
| I/O | ‑‑proposed‑variants PROPOSED_VARIANTS | No | Path of the VCF file, which has proposed variants for the make examples stage. |
| Tool | ‑‑preset PRESET | No | Which preset to apply. Possible values are {map-pbmm2,map-hifi,map-ont,splice,splice:hq}. 'map-pbmm2' is a customized preset that uses pbmm2's default values for PacBio HiFi/CCS genomic reads. 'map-hifi' is minimap2's default preset for PacBio HiFi/CCS genomic reads. 'map-ont' is for Oxford Nanopore genomic reads. 'splice' is for spliced long reads (strand unknown). 'splice:hq' is for Final PacBio Iso-seq or traditional cDNA. (default: map-pbmm2) |
| Tool | ‑‑pbmm2 | No | Include additional processing to match the format and accuracy of pbmm2. Not compatible with map-ont --preset value. |
| Tool | ‑‑pbmm2‑unmapped | No | Include unmapped records in output of pbmm2. Must be used concurrently with --pbmm2. Not compatible with map-ont --preset value. |
| Tool | ‑k MINIMIZER_KMER_LEN, ‑‑minimizer‑kmer‑len MINIMIZER_KMER_LEN | No | Minimizer k-mer length. |
| Tool | ‑uf, ‑‑forward‑transcript‑strand | No | Force minimap2 to consider the forward transcript strand only when finding canonical splicing sites GT-AG. |
| Tool | ‑‑eqx | No | Write =/X CIGAR operators. |
| Tool | ‑L INTERVAL, ‑‑interval INTERVAL | No | Interval within which to call bqsr from the input reads. All intervals will have a padding of 100 to get read records, and overlapping intervals will be combined. Interval files should be passed using the --interval-file option. This option can be used multiple times (e.g. "-L chr1 -L chr2:10000 -L chr3:20000+ -L chr4:10000-20000"). |
| Tool | ‑ip INTERVAL_PADDING, ‑‑interval‑padding INTERVAL_PADDING | No | Amount of padding (in base pairs) to add to each interval you are including. |
| Tool | ‑‑standalone‑bqsr | No | Run standalone BQSR after generating sorted BAM. This option requires both --knownSites and --out-recal-file input parameters. |
| Tool | ‑‑read‑group‑sm READ_GROUP_SM | No | SM tag for read groups in this run. |
| Tool | ‑‑read‑group‑lb READ_GROUP_LB | No | LB tag for read groups in this run. |
| Tool | ‑‑read‑group‑pl READ_GROUP_PL | No | PL tag for read groups in this run. |
| Tool | ‑‑read‑group‑id‑prefix READ_GROUP_ID_PREFIX | No | Prefix for the ID and PU tags for read groups in this run. This prefix will be used for all pairs of FASTQ files in this run. The ID and PU tags will consist of this prefix and an identifier, that will be unique for a pair of FASTQ files. |
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
| Performance | ‑‑num‑threads NUM_THREADS | No | Number of processing threads. (default: 28) |
| Performance | ‑‑nstreams NSTREAMS | No | Number of streams to use per GPU. (default: 2) |
| Performance | ‑‑gpuwrite | No | Use one GPU to accelerate writing final BAM/CRAM. |
| Performance | ‑‑gpuwrite‑deflate‑algo GPUWRITE_DEFLATE_ALGO | No | Choose the nvCOMP DEFLATE algorithm to use with --gpuwrite. Note these options do not correspond to CPU DEFLATE options. Valid options are 1, 2, and 4. Option 1 is fastest, while options 2 and 4 have progressively lower throughput but higher compression ratios. The default value is 1 when the user does not provide an input (i.e., None). |
| Performance | ‑‑gpusort | No | Use GPUs to accelerate sorting. |
| Performance | ‑‑use‑gds | No | Use GPUDirect Storage (GDS) to enable a direct data path for direct memory access (DMA) transfers between GPU memory and storage. Must be used concurrently with --gpuwrite. Please refer to Parabricks Documentation > Best Performance for information on how to set up and use GPUDirect Storage. |
| Performance | ‑‑max‑queue‑reads MAX_QUEUE_READS | No | Max number of reads to allow in the alignment processing stage. Increasing this value may result in faster processing, but it will use more host memory. (default: 500000) |
| Performance | ‑‑low‑memory | No | Use low memory mode. |
| Performance | ‑‑chunk‑size CHUNK_SIZE | No | Max number of reads in a processing chunk. Increasing this value may result in faster processing for splice presets, but it will use more host memory. (default: 5000) |
| Performance | ‑‑num‑cpu‑threads‑per‑stream NUM_CPU_THREADS_PER_STREAM | No | Number of CPU threads to use per stream. (default: 6) |
| Performance | ‑‑num‑streams‑per‑gpu NUM_STREAMS_PER_GPU | No | Number of streams to use per GPU. Default is 'auto' which will try to use an optimal amount of streams based on the GPU. (default: auto) |
| Performance | ‑‑run‑partition | No | Divide the whole genome into multiple partitions and run multiple processes at the same time, each on one partition. |
| Performance | ‑‑gpu‑num‑per‑partition GPU_NUM_PER_PARTITION | No | Number of GPUs to use per partition. |
| Performance | ‑‑max‑reads‑per‑partition MAX_READS_PER_PARTITION | No | The maximum number of reads per partition that are considered before following processing such as sampling and realignment. (default: 1500) |
| Performance | ‑‑partition‑size PARTITION_SIZE | No | The maximum number of basepairs allowed in a region before splitting it into multiple smaller subregions. (default: 1000) |
| Performance | ‑‑use‑tf32 | No | Enable inference optimization using Tensor Float 32(TF32) on ampere+ gpu. Note that this might introduce a few mismatches in the output VCF. |
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



