# rna_fq2bam

This tool is the equivalent of fq2bam for RNA-Seq samples, receiving inputs in FASTQ format, performing alignment with the splice-aware STAR algorithm, optionally marking of duplicate reads, and outputting an aligned BAM file ready for variant and fusion calling.



See the rna_fq2bam Reference section for a detailed listing of all available options.



### Quick Start
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun rna_fq2bam \
    --in-fq /workdir/${INPUT_FASTQ_1} /workdir/${INPUT_FASTQ_2} \
    --genome-lib-dir /workdir/${PATH_TO_GENOME_LIBRARY}/ \
    --output-dir /outputdir/${PATH_TO_OUTPUT_DIRECTORY} \
    --ref /workdir/${REFERENCE_FILE} \
    --out-bam /outputdir/${OUTPUT_BAM} \
    --read-files-command zcat



### Compatible CPU Command
The output from these commands will be identical to the output from the above command. See the Output Comparison page for comparing the results.

# STAR Alignment
$ ./STAR \
      --genomeDir <INPUT_DIR>/${PATH_TO_GENOME_LIBRARY} \
      --readFilesIn <INPUT_DIR>/${INPUT_FASTQ_1} <INPUT_DIR>/${INPUT_FASTQ_2} \
      --outFileNamePrefix <OUTPUT_DIR>/${PATH_TO_OUTPUT_DIRECTORY}/ \
      --outSAMtype BAM SortedByCoordinate \
      --readFilesCommand zcat

# Mark Duplicates
$ gatk MarkDuplicates \
    --java-options -Xmx30g \
    -I Aligned.sortedByCoord.out.bam \# This filename is determined by STAR.
    -O <OUTPUT_DIR>/${NAME_OF_OUTPUT_BAM_FILE} \
    -M metrics.txt


Note
Make sure you have the same version of STAR installed that was used to build the genome index.

The Parabricks version of STAR is compatible with the 2.7.2a CPU-only version of STAR.


Deterministic Primary Alignment Selection in quantMode TranscriptomeSAM

Parabricks uses a deterministic approach for selecting primary alignments (which affects the samFlag in the BAM record) among alignments in the Aligned.toTranscriptome.bam file during the quantMode TranscriptomeSAM mode.

To compare the Parabricks version with the baseline STAR, the following modification is required in the baseline STAR code:

# Add this line in ReadAlign::quantTranscriptome() function in ReadAlign_quantTranscriptome.cpp
rngMultOrder.seed(777);
# Add it right before:
alignT[int(rngUniformReal0to1(rngMultOrder)*nAlignT)].primaryFlag=true;


Warning
Known Issue with Linux Kernel 6.11.0: There is a known issue with pinned memory allocation in Linux kernel 6.11.0 that may cause problems with this tool. For more details, see the NVIDIA Developer Forums discussion. It is recommended to avoid using kernel version 6.11.0.



## rna_fq2bam Reference
Run RNA-seq data through the fq2bam pipeline. It will run STAR aligner, co- ordinate sorting and mark duplicates.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑fq [IN_FQ ...] | No | Path to the pair-ended FASTQ files followed by optional read groups with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:sampletPU:foo"). The files must be in fastq or fastq.gz format. All sets of inputs should have a read group; otherwise, none should have a read group, and it will be automatically added by the pipeline. This option can be repeated multiple times. Example 1: --in-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz --in-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz. Example 2: --in-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz "@RGtID:footLB:lib1tPL:bartSM:sampletPU:unit1" --in-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz "@RGtID:foo2tLB:lib1tPL:bartSM:sampletPU:unit2". For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑in‑se‑fq [IN_SE_FQ ...] | No | Path to the single-ended FASTQ file followed by optional read group with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:sampletPU:foo"). The file must be in fastq or fastq.gz format. Either all sets of inputs have a read group, or none should have one, and it will be automatically added by the pipeline. This option can be repeated multiple times. Example 1: --in-se-fq sampleX_1.fastq.gz --in-se-fq sampleX_2.fastq.gz . Example 2: --in-se-fq sampleX_1.fastq.gz "@RGtID:footLB:lib1tPL:bartSM:sampletPU:unit1" --in-se-fq sampleX_2.fastq.gz "@RGtID:foo2tLB:lib1tPL:bartSM:sampletPU:unit2" . For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑in‑fq‑list IN_FQ_LIST | No | Path to a file that contains the locations of pair-ended FASTQ files. Each line must contain the location of two FASTQ files followed by an optional read group, each separated by a space. Each set of files (and associated read group) must be on a separate line. Files must be in fastq/fastq.gz format. Line syntax: |
| I/O | ‑‑in‑se‑fq‑list IN_SE_FQ_LIST | No | Path to a file that contains the locations of single-ended FASTQ files. Each line must contain the location of the FASTQ files followed by an optional read group, each separated by a space. Each file (and associated read group) must be on a separate line. Files must be in fastq/fastq.gz format. Line syntax: |
| I/O | ‑‑genome‑lib‑dir GENOME_LIB_DIR | Yes | Path to a genome resource library directory. The indexing required to run STAR should be completed by the user beforehand. |
| I/O | ‑‑output‑dir OUTPUT_DIR | Yes | Path to the directory that will contain all of the generated files. |
| I/O | ‑‑out‑bam OUT_BAM | Yes | Path of the output BAM file. |
| I/O | ‑‑out‑duplicate‑metrics OUT_DUPLICATE_METRICS | No | Path of duplicate metrics file after marking duplicates. |
| I/O | ‑‑out‑qc‑metrics‑dir OUT_QC_METRICS_DIR | No | Path of the directory where QC metrics will be generated. |
| Tool | ‑‑out‑prefix OUT_PREFIX | No | Prefix filename for output data. |
| Tool | ‑‑read‑files‑command READ_FILES_COMMAND | No | Command line to execute for each of the input files. This command should generate FASTA or FASTQ text and send it to stdout: For example, zcat to uncompress .gz files, bzcat to uncompress .bz2 files, etc. |
| Tool | ‑‑read‑group‑sm READ_GROUP_SM | No | SM tag for read groups in this run. |
| Tool | ‑‑read‑group‑lb READ_GROUP_LB | No | LB tag for read groups in this run. |
| Tool | ‑‑read‑group‑pl READ_GROUP_PL | No | PL tag for read groups in this run. |
| Tool | ‑‑read‑group‑id‑prefix READ_GROUP_ID_PREFIX | No | Prefix for the ID and PU tags for read groups in this run. This prefix will be used for all pairs of FASTQ files in this run. The ID and PU tags will consist of this prefix and an identifier that will be unique for a pair of FASTQ files. |
| Tool | ‑‑num‑sa‑bases NUM_SA_BASES | No | Length (bases) of the SA pre-indexing string. Longer strings will use more memory, but allow for faster searches. A value between 10 and 15 is recommended. For small genomes, the parameter must be scaled down to min(14, log2(GenomeLength)/2 - 1). (default: 14) |
| Tool | ‑‑max‑intron‑size MAX_INTRON_SIZE | No | Maximum align intron size. If this value is 0, the maximum size will be determined by (2^winBinNbits)*winAnchorDistNbins. (default: 0) |
| Tool | ‑‑min‑intron‑size MIN_INTRON_SIZE | No | Minimum align intron size. Genomic gap is considered intron if its length is greater than or equal to this value, otherwise it is considered Deletion. (default: 21) |
| Tool | ‑‑min‑match‑filter MIN_MATCH_FILTER | No | Minimum number of matched bases required for alignment output. (default: 0) |
| Tool | ‑‑min‑match‑filter‑normalized MIN_MATCH_FILTER_NORMALIZED | No | Same as --min-match-filter, but normalized to the read length (sum of the mate lengths for paired-end reads). (default: 0.66) |
| Tool | ‑‑out‑filter‑intron‑motifs OUT_FILTER_INTRON_MOTIFS | No | Type of filter alignment using its motifs. This string can be "None" for no filtering, "RemoveNoncanonical" for filtering out alignments that contain non-canonical junctions, or "RemoveNoncanonicalUnannotated" for filtering out alignments that contain non-canonical unannotated junctions when using the annotated splice junctions database. The annotated non-canonical junctions will be kept. (default: None) |
| Tool | ‑‑max‑out‑filter‑mismatch MAX_OUT_FILTER_MISMATCH | No | Maximum number of mismatches allowed for an alignment to be output. (default: 10) |
| Tool | ‑‑max‑out‑filter‑mismatch‑ratio MAX_OUT_FILTER_MISMATCH_RATIO | No | Maximum ratio of mismatches to mapped length allowed for an alignment to be output. (default: 0.3) |
| Tool | ‑‑max‑out‑filter‑multimap MAX_OUT_FILTER_MULTIMAP | No | Maximum number of loci the read is allowed to map to for all alignments to be output. Otherwise, no alignments will be output and the read will be counted as "mapped to too many loci" in the Log.final.out. (default: 10) |
| Tool | ‑‑out‑reads‑unmapped OUT_READS_UNMAPPED | No | Type of output of unmapped and partially mapped (i.e. mapped only one mate of a paired-end read) reads in separate file(s). This string can be "None" for no output or "Fastx" for output in separate FASTA/FASTQ files, Unmapped.out.mate1/2. (default: None) |
| Tool | ‑‑out‑sam‑unmapped OUT_SAM_UNMAPPED | No | Type of output of unmapped reads in SAM format. The string can be "None" to produce no output, "Within" to output unmapped reads within the main SAM file. Option "Within_KeepPairs" will produce the same result as "Within" because unmapped mates are ignored for sorted SAM/BAM output such as the output produced by this tool. (default: None) |
| Tool | ‑‑out‑sam‑attributes OUT_SAM_ATTRIBUTES [OUT_SAM_ATTRIBUTES ...] | No | A string of SAM attributes in the order desired for the output SAM. The string can contain any combination of the following attributes: {NH, HI, AS, nM, NM, MD, jM, jI, XS, MC, ch}. Alternatively, the string can be "None" for no attributes, "Standard" for the attributes {NH, HI, AS, nM}, or "All" for the attributes {NH, HI, AS, nM, NM, MD, jM, jI, MC, ch} (e.g. "--outSAMattributes NH nM jI XS ch"). (default: Standard) |
| Tool | ‑‑out‑sam‑strand‑field OUT_SAM_STRAND_FIELD | No | Cufflinks-like strand field flag. The string can be "None" for no flag or "intronMotif" for the strand derived from the intron motif. Reads with inconsistent and/or non-canonical introns will be filtered out. (default: None) |
| Tool | ‑‑out‑sam‑mode OUT_SAM_MODE | No | SAM output mode. The string can be "None" for no SAM output, "Full" for full SAM output, or "NoQS" for full SAM output without quality scores. (default: Full) |
| Tool | ‑‑out‑sam‑mapq‑unique OUT_SAM_MAPQ_UNIQUE | No | The MAPQ value for unique mappers. Must be in the range [0, 255]. (default: 255) |
| Tool | ‑‑min‑score‑filter MIN_SCORE_FILTER | No | Minimum score required for alignment output, normalized to the read length (i.e. the sum of mate lengths for paired-end reads). (default: 0.66) |
| Tool | ‑‑min‑spliced‑mate‑length MIN_SPLICED_MATE_LENGTH | No | Minimum mapped length for a read mate that is spliced and normalized to the mate length. Must be greater than 0. (default: 0.66) |
| Tool | ‑‑max‑junction‑mismatches MAX_JUNCTION_MISMATCHES MAX_JUNCTION_MISMATCHES MAX_JUNCTION_MISMATCHES MAX_JUNCTION_MISMATCHES | No | Maximum number of mismatches for stitching of the splice junctions. A limit must be specified for each of the following: (1) non-canonical motifs, (2) GT/AG and CT/AC motif, (3) GC/AG and CT/GC motif, (4) AT/AC and GT/AT motif. To indicate no limit for any of the four options, use -1. (default: [0, -1, 0, 0]) |
| Tool | ‑‑max‑out‑read‑size MAX_OUT_READ_SIZE | No | Maximum size of the SAM record (bytes) for one read. Recommended value: > 2*(LengthMate1+LengthMate2+100)*outFilterMultimapNmax. Must be greater than 0. (default: 100000) |
| Tool | ‑‑max‑alignments‑per‑read MAX_ALIGNMENTS_PER_READ | No | Maximum number of different alignments per read to consider. Must be greater than 0. (default: 10000) |
| Tool | ‑‑score‑gap SCORE_GAP | No | Splice junction penalty (independent of intron motif). (default: 0) |
| Tool | ‑‑seed‑search‑start SEED_SEARCH_START | No | Defines the search start point through the read. The read split pieces will not be longer than this value. Must be greater than 0. (default: 50) |
| Tool | ‑‑max‑bam‑sort‑memory MAX_BAM_SORT_MEMORY | No | Maximum available RAM (bytes) for sorting BAM. If this value is 0, it will be set to the genome index size. Must be greater than or equal to 0. (default: 0) |
| Tool | ‑‑align‑ends‑type ALIGN_ENDS_TYPE | No | Type of read ends alignment. Can be one of two options: "Local" will perform a standard local alignment with soft-clipping allowed; "EndToEnd" will force an end-to-end read alignment with no soft-clipping. (default: Local) |
| Tool | ‑‑align‑insertion‑flush ALIGN_INSERTION_FLUSH | No | Flush ambiguous insertion positions. The string can be "None" to not flush insertions or "Right" to flush insertions to the right. (default: None) |
| Tool | ‑‑max‑align‑mates‑gap MAX_ALIGN_MATES_GAP | No | Maximum gap between two mates. If 0, the max intron gap will be determined by (2^winBinNbits)*winAnchorDistNbins. (default: 0) |
| Tool | ‑‑min‑align‑spliced‑mate‑map MIN_ALIGN_SPLICED_MATE_MAP | No | Minimum mapped length for a read mate that is spliced. Must be greater than or equal to 0. (default: 0) |
| Tool | ‑‑max‑collapsed‑junctions MAX_COLLAPSED_JUNCTIONS | No | Maximum number of collapsed junctions. Must be greater than 0. (default: 1000000) |
| Tool | ‑‑min‑align‑sj‑overhang MIN_ALIGN_SJ_OVERHANG | No | Minimum overhang (i.e. block size) for spliced alignments. Must be greater than 0. (default: 5) |
| Tool | ‑‑min‑align‑sjdb‑overhang MIN_ALIGN_SJDB_OVERHANG | No | Minimum overhang (i.e. block size) for annotated (sjdb) spliced alignments. Must be greater than 0. (default: 3) |
| Tool | ‑‑sjdb‑overhang SJDB_OVERHANG | No | Length of the donor/acceptor sequence on each side of the junctions. Ideally, this value should be equal to mate_length - 1. Must be greater than 0. (default: 100) |
| Tool | ‑‑min‑chim‑overhang MIN_CHIM_OVERHANG | No | Minimum overhang for the Chimeric.out.junction file. Must be greater than or equal to 0. (default: 20) |
| Tool | ‑‑min‑chim‑segment MIN_CHIM_SEGMENT | No | Minimum chimeric segment length. If it is set to 0, there will be no chimeric output. Must be greater than or equal to 0. (default: 0) |
| Tool | ‑‑max‑chim‑multimap MAX_CHIM_MULTIMAP | No | Maximum number of chimeric multi-alignments. If it is set to 0, the old scheme for chimeric detection, which only considered unique alignments, will be used. Must be greater than or equal to 0. (default: 0) |
| Tool | ‑‑chim‑multimap‑score‑range CHIM_MULTIMAP_SCORE_RANGE | No | The score range for multi-mapping chimeras below the best chimeric score. This option only works with --max-chim-multimap > 1. Must be greater than or equal to 0. (default: 1) |
| Tool | ‑‑chim‑score‑non‑gtag CHIM_SCORE_NON_GTAG | No | The penalty for a non-GT/AG chimeric junction. (default: -1) |
| Tool | ‑‑min‑non‑chim‑score‑drop MIN_NON_CHIM_SCORE_DROP | No | To trigger chimeric detection, the drop in the best non-chimeric alignment score with respect to the read length has to be smaller than this value. Must be greater than or equal to 0. (default: 20) |
| Tool | ‑‑out‑chim‑format OUT_CHIM_FORMAT | No | Formatting type for the Chimeric.out.junction file. Possible types are {0, 1}. If type 0, there will be no comment lines/headers. If type 1, there will be comment lines at the end of the file: command line and Nreads: total, unique, multi. (default: 0) |
| Tool | ‑‑two‑pass‑mode TWO_PASS_MODE | No | Two-pass mapping mode. The string can be "None" for one-pass mapping or "Basic" for basic two-pass mapping, with all first pass junctions inserted into the genome indices on the fly. (default: None) |
| Tool | ‑‑out‑chim‑type OUT_CHIM_TYPE | No | Type of chimeric output. This string can be "Junctions" for Chimeric.out.junction, "WithinBAM" for main aligned BAM files (Aligned.*.bam), "WithinBAM_HardClip" for hard-clipping in the CIGAR for supplemental chimeric alignments, or "WithinBAM_SoftClip" for soft-clipping in the CIGAR for supplemental chimeric alignments. |
| Tool | ‑‑no‑markdups | No | Do not perform the Mark Duplicates step. Return BAM after sorting. |
| Tool | ‑‑read‑name‑separator READ_NAME_SEPARATOR [READ_NAME_SEPARATOR ...] | No | Character(s) separating the part of the read names that will be trimmed in output (read name after space is always trimmed). (default: /) |
| Tool | ‑‑soloType | No | SOLOTYPE Type of single-cell RNA-seq. Can be "None" for no single-cell RNA-seq or "Droplet" for droplet single-cell RNA-seq. (default: None) |
| Tool | ‑‑soloBarcodeReadLength SOLOBARCODEREADLENGTH | No | Length of the barcode read (the read containing cell barcode and UMI). If set to 0, barcode length equals the sum of cell barcode and UMI lengths. (default: 0) |
| Tool | ‑‑soloCBwhitelist SOLOCBWHITELIST | No | Path to file containing whitelist of cell barcodes. Required for --soloType Droplet. |
| Tool | ‑‑soloCBstart SOLOCBSTART | No | Cell barcode start position (1-based) in the barcode read. (default: 1) |
| Tool | ‑‑soloCBlen SOLOCBLEN | No | Cell barcode length. (default: 16) |
| Tool | ‑‑soloUMIstart SOLOUMISTART | No | UMI start position (1-based) in the barcode read. (default: 17) |
| Tool | ‑‑soloUMIlen SOLOUMILEN | No | UMI length. (default: 10) |
| Tool | ‑‑soloFeatures SOLOFEATURES [SOLOFEATURES ...] | No | Features type for which the UMI counts per Cell Barcode are collected. Can include one or more of: Gene, SJ, GeneFull. (default: ['Gene']) |
| Tool | ‑‑soloStrand SOLOSTRAND | No | Strand for UMI-deduplication. Can be "Unstranded", "Forward", or "Reverse". (default: Forward) |
| Tool | ‑‑quantMode QUANTMODE [QUANTMODE ...] | No | Types of quantification requested. Can include: TranscriptomeSAM - output SAM/BAM alignments to transcriptome into a separate file, GeneCounts - output gene counts in ReadsPerGene.out.tab file |
| Performance | ‑‑num‑threads NUM_THREADS | No | Number of worker threads per GPU stream. (default: 4) |
| Performance | ‑‑enable‑gpu‑helper‑threads ENABLE_GPU_HELPER_THREADS | No | Number of worker threads that are enabled to share workload with the GPU. A small number of such threads can improve the overall performance on GPUs with lower compute capabilities. (default: 0) |
| Performance | ‑‑num‑streams‑per‑gpu NUM_STREAMS_PER_GPU | No | Number of streams per GPU. (default: 2) |
| Performance | ‑‑gpuwrite | No | Use one GPU to accelerate writing final BAM/CRAM. |
| Performance | ‑‑gpuwrite‑deflate‑algo GPUWRITE_DEFLATE_ALGO | No | Choose the nvCOMP DEFLATE algorithm to use with --gpuwrite. Note these options do not correspond to CPU DEFLATE options. Valid options are 1, 2, and 4. Option 1 is fastest, while options 2 and 4 have progressively lower throughput but higher compression ratios. The default value is 1 when the user does not provide an input (i.e., None) |
| Performance | ‑‑gpusort | No | Use GPUs to accelerate sorting and marking. |
| Performance | ‑‑use‑gds | No | Use GPUDirect Storage (GDS) to enable a direct data path for direct memory access (DMA) transfers between GPU memory and storage. Must be used concurrently with --gpuwrite. Please refer to Parabricks Documentation > Best Performance for information on how to set up and use GPUDirect Storage. |
| Performance | ‑‑memory‑limit MEMORY_LIMIT | No | System memory limit in GBs during sorting and postsorting. By default, the limit is half of the total system memory. (default: 62) |
| Performance | ‑‑low‑memory | No | Use low memory mode. (default: False) |
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

somatic (Somatic Variant Caller)
Run a somatic variant workflow.



The somatic tool processes the tumor FASTQ files, and optionally normal FASTQ files and knownSites files, and generates tumor or tumor/normal analysis. The output is in VCF format.

Internally the somatic tool runs several other Parabricks tools, thereby simplifying your work flow.


somatic.png


See the somatic Reference section for a detailed listing of all available options.



### Quick Start
# The command line below will run tumor-only analysis.
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun somatic \
    --ref /workdir/${REFERENCE_FILE} \
    --in-tumor-fq /workdir/${INPUT_FASTQ_1} /workdir/${INPUT_FASTQ_2} \
    --bwa-options="-Y" \
    --out-vcf /outputdir/${OUTPUT_VCF} \
    --out-tumor-bam /outputdir/${OUTPUT_BAM}

# The command line below will run tumor-normal analysis.
# This command assumes all the inputs are in the current working directory and all the outputs go to the same place.
docker run --rm --gpus all --volume $(pwd):/workdir --volume $(pwd):/outputdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 \
    pbrun somatic \
    --ref /workdir/${REFERENCE_FILE} \
    --knownSites /workdir/${KNOWN_SITES_FILE} \
    --in-tumor-fq /workdir/${INPUT_TUMOR_FASTQ_1} /workdir/${INPUT_TUMOR_FASTQ_2} "@RG\tID:sm_tumor_rg1\tLB:lib1\tPL:bar\tSM:sm_tumor\tPU:sm_tumor_rg1" \
    --bwa-options="-Y" \
    --out-vcf /outputdir/${OUTPUT_VCF} \
    --out-tumor-bam /outputdir/${OUTPUT_TUMOR_BAM} \
    --out-tumor-recal-file /outputdir/${OUTPUT_RECAL_FILE} \
    --in-normal-fq /workdir/${INPUT_NORMAL_FASTQ_1} /workdir/${INPUT_NORMAL_FASTQ_2} "@RG\tID:sm_normal_rg1\tLB:lib1\tPL:bar\tSM:sm_normal\tPU:sm_normal_rg1" \
    --out-normal-bam /outputdir/${OUTPUT_NORMAL_BAM}



### Compatible CPU Command

| Type | Name | Required? | Description |
|------|------|-----------|-------------|

  gatk SortSam \
    --java-options -Xmx30g \
    --MAX_RECORDS_IN_RAM 5000000 \
    -I /dev/stdin \
    -O tumor_cpu.bam \
    --SORT_ORDER coordinate

# Mark duplicates.
$ gatk MarkDuplicates \
    --java-options -Xmx30g \
    -I tumor_cpu.bam \
    -O tumor_mark_dups_cpu.bam \
    -M tumor_metrics.txt

# Generate a BQSR report.
$ gatk BaseRecalibrator \
    --java-options -Xmx30g \
    --input tumor_mark_dups_cpu.bam \
    --output ${OUTPUT_TUMOR_RECAL_FILE} \
    --known-sites ${KNOWN_SITES_FILE} \
    --reference ${REFERENCE_FILE}

# Apply the BQSR report.
$ gatk ApplyBQSR \
    --java-options -Xmx30g \
    -R ${REFERENCE_FILE} \
    -I tumor_cpu.bam \
    --bqsr-recal-file ${TUMOR_OUTPUT_RECAL_FILE} \
    -O ${OUTPUT_TUMOR_BAM}

# Now repeat all the above steps, only with the normal FASTQ data.
$ bwa mem \
    -t 32 \
    -K 10000000 \
    -Y \
    -R '@RG\tID:sample_rg1\tLB:lib1\tPL:bar\tSM:sample\tPU:sample_rg1' \
    ${REFERENCE_FILE} ${NORMAL_FASTQ_1} ${NORMAL_FASTQ_2} | \
  gatk SortSam \
    --java-options -Xmx30g \
    --MAX_RECORDS_IN_RAM 5000000 \
    -I /dev/stdin \
    -O normal_cpu.bam \
    --SORT_ORDER coordinate

# Mark duplicates.
$ gatk MarkDuplicates \
    --java-options -Xmx30g \
    -I normal_cpu.bam \
    -O normal_mark_dups_cpu.bam \
    -M normal_metrics.txt

# Generate a BQSR report.
$ gatk BaseRecalibrator \
    --java-options -Xmx30g \
    --input normal_mark_dups_cpu.bam \
    --output ${OUTPUT_NORMAL_RECAL_FILE} \
    --known-sites ${KNOWN_SITES_FILE} \
    --reference ${REFERENCE_FILE}

# Apply the BQSR report.
$ gatk ApplyBQSR \
    --java-options -Xmx30g \
    -R ${REFERENCE_FILE} \
    -I normal_cpu.bam \
    --bqsr-recal-file ${OUTPUT_NORMAL_RECAL_FILE} \
    -O ${OUTPUT_NORMAL_BAM}

# Finally, run Mutect2 on the normal and tumor data.
$ gatk Mutect2 \
    -R ${REFERENCE_FILE} \
    --input ${OUTPUT_TUMOR_BAM} \
    --tumor-sample tumor \
    --input ${OUTPUT_NORMAL_BAM} \
    --normal-sample normal \
    --output ${OUTPUT_VCF}



## somatic Reference
Run the tumor normal somatic pipeline from FASTQ to VCF.




| Type | Name | Required? | Description |
|------|------|-----------|-------------|
| I/O | ‑‑ref REF | Yes | Path to the reference file. |
| I/O | ‑‑in‑tumor‑fq [IN_TUMOR_FQ ...] | No | Path to the pair-ended FASTQ files followed by optional read group with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:20"). The files can be in fastq or fastq.gz format. Either all sets of inputs have a read group, or none should have one, and it will be automatically added by the pipeline. This option can be repeated multiple times. Example 1: --in-tumor-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz --in-tumor-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz. Example 2: --in-tumor-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz "@RG ID:footLB:lib1tPL:bartSM:sm_tumortPU:unit1" --in-tumor-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz "@RG ID:foo2tLB:lib1tPL:bartSM:sm_tumortPU:unit2". For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑in‑se‑tumor‑fq [IN_SE_TUMOR_FQ ...] | No | Path to the single-ended FASTQ file followed by an optional read group with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:sampletPU:foo"). The file must be in fastq or fastq.gz format. Either all sets of inputs have a read group, or none should have one; if no read group is provided, one will be added automatically by the pipeline. This option can be repeated multiple times. Example 1: --in-se-tumor-fq sampleX_1.fastq.gz --in-se-tumor-fq sampleX_2.fastq.gz . Example 2: --in-se-tumor-fq sampleX_1.fastq.gz "@RGtID:footLB:lib1tPL:bartSM:tumortPU:unit1" --in-se-tumor-fq sampleX_2.fastq.gz "@RGtID:foo2tLB:lib1tPL:bartSM:tumortPU:unit2" . For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑in‑normal‑fq [IN_NORMAL_FQ ...] | No | Path to the pair-ended FASTQ files followed by an optional read group with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:20"). The files must be in fastq or fastq.gz format. Either all sets of inputs have a read group, or none should have one; if no read group is provided, one will be automatically added by the pipeline. This option can be repeated multiple times. Example 1: --in-normal-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz --in-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz . Example 2: --in-normal-fq sampleX_1_1.fastq.gz sampleX_1_2.fastq.gz "@RG ID:footLB:lib1tPL:bartSM:sm_normaltPU:unit1" --in-normal-fq sampleX_2_1.fastq.gz sampleX_2_2.fastq.gz "@RG ID:foo2tLB:lib1tPL:bartSM:sm_normaltPU:unit2". For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑in‑se‑normal‑fq [IN_SE_NORMAL_FQ ...] | No | Path to the single-ended FASTQ file followed by optional read group with quotes (Example: "@RGtID:footLB:lib1tPL:bartSM:sampletPU:foo"). The file must be in fastq or fastq.gz format. Either all sets of inputs have a read group, or none should have one; if no read group is provided, one will be added automatically by the pipeline. This option can be repeated multiple times. Example 1: --in-se-normal-fq sampleX_1.fastq.gz --in-se-normal-fq sampleX_2.fastq.gz . Example 2: --in-se-normal-fq sampleX_1.fastq.gz "@RGtID:footLB:lib1tPL:bartSM:normaltPU:unit1" --in-se-normal-fq sampleX_2.fastq.gz "@RGtID:foo2tLB:lib1tPL:bartSM:normaltPU:unit2" . For the same sample, Read Groups should have the same sample name (SM) and a different ID and PU. |
| I/O | ‑‑knownSites KNOWNSITES | No | Path to a known indels file. The file must be in vcf.gz format. This option can be used multiple times. |
| I/O | ‑‑interval‑file INTERVAL_FILE | No | Path to an interval file in one of these formats: Picard-style (.interval_list or .picard), GATK-style (.list or .intervals), or BED file (.bed). This option can be used multiple times. |
| I/O | ‑‑out‑vcf OUT_VCF | Yes | Path of the VCF file after Variant Calling. (Allowed: .vcf, .vcf.gz) |
| I/O | ‑‑out‑tumor‑bam OUT_TUMOR_BAM | Yes | Path of the BAM file for tumor reads. |
| I/O | ‑‑out‑normal‑bam OUT_NORMAL_BAM | No | Path of the BAM file for normal reads. |
| I/O | ‑‑mutect‑bam‑output MUTECT_BAM_OUTPUT | No | File to which assembled haplotypes should be written in Mutect. If passing with --run-partition, multiple BAM files will be written. |
| I/O | ‑‑out‑tumor‑recal‑file OUT_TUMOR_RECAL_FILE | No | Path of the report file after Base Quality Score Recalibration for tumor sample. |
| I/O | ‑‑out‑normal‑recal‑file OUT_NORMAL_RECAL_FILE | No | Path of the report file after Base Quality Score Recalibration for normal sample. |
| I/O | ‑‑mutect‑germline‑resource MUTECT_GERMLINE_RESOURCE | No | Path of the vcf.gz germline resource file. Population VCF of germline sequencing containing allele fractions. |
| I/O | ‑‑mutect‑alleles MUTECT_ALLELES | No | Path of the vcf.gz force-call file. The set of alleles to force-call regardless of evidence. |
| I/O | ‑‑mutect‑f1r2‑tar‑gz MUTECT_F1R2_TAR_GZ | No | Path of the tar.gz of collecting F1R2 counts. |
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
| Tool | ‑ip INTERVAL_PADDING, ‑‑interval‑padding INTERVAL_PADDING | No | Amount of padding (in base pairs) to add to each interval you are including. |
| Tool | ‑‑standalone‑bqsr | No | Run standalone BQSR. |
| Tool | ‑‑max‑mnp‑distance MAX_MNP_DISTANCE | No | Two or more phased substitutions separated by this distance or less are merged into MNPs. (default: 1) |
| Tool | ‑‑mutectcaller‑options MUTECTCALLER_OPTIONS | No | Pass supported mutectcaller options as one string. The following are currently supported original mutectcaller options: -pcr-indel-model , -max-reads-per-alignment-start , -A , -min-dangling-branch-length (e.g. --mutectcaller-options="-pcr-indel-model HOSTILE -max-reads-per-alignment-start 30"). |
| Tool | ‑‑initial‑tumor‑lod INITIAL_TUMOR_LOD | No | Log 10 odds threshold to consider pileup active. |
| Tool | ‑‑tumor‑lod‑to‑emit TUMOR_LOD_TO_EMIT | No | Log 10 odds threshold to emit variant to VCF. |
| Tool | ‑‑pruning‑lod‑threshold PRUNING_LOD_THRESHOLD | No | Ln likelihood ratio threshold for adaptive pruning algorithm. |
| Tool | ‑‑active‑probability‑threshold ACTIVE_PROBABILITY_THRESHOLD | No | Minimum probability for a locus to be considered active. |
| Tool | ‑‑no‑alt‑contigs | No | Ignore commonly known alternate contigs. |
| Tool | ‑‑genotype‑germline‑sites | No | Call all apparent germline site even though they will ultimately be filtered. |
| Tool | ‑‑genotype‑pon‑sites | No | Call sites in the PoN even though they will ultimately be filtered. |
| Tool | ‑‑force‑call‑filtered‑alleles | No | Force-call filtered alleles included in the resource specified by --alleles. |
| Tool | ‑‑filter‑reads‑too‑long | No | Ignore all input BAM reads with size > 500bp. |
| Tool | ‑‑minimum‑mapping‑quality MINIMUM_MAPPING_QUALITY | No | Minimum mapping quality to keep (inclusive). |
| Tool | ‑‑min‑base‑quality‑score MIN_BASE_QUALITY_SCORE | No | Minimum base quality required to consider a base for calling. |
| Tool | ‑‑f1r2‑median‑mq F1R2_MEDIAN_MQ | No | skip sites with median mapping quality below this value. |
| Tool | ‑‑base‑quality‑score‑threshold BASE_QUALITY_SCORE_THRESHOLD | No | Base qualities below this threshold will be reduced to the minimum (6). |
| Tool | ‑‑normal‑lod NORMAL_LOD | No | Log 10 odds threshold for calling normal variant non-germline. |
| Tool | ‑‑allow‑non‑unique‑kmers‑in‑ref | No | Allow graphs that have non-unique kmers in the reference. |
| Tool | ‑‑enable‑dynamic‑read‑disqualification‑for‑genotyping | No | Will enable less strict read disqualification low base quality reads. |
| Tool | ‑‑recover‑all‑dangling‑branches | No | Recover all dangling branches. |
| Tool | ‑‑pileup‑detection | No | If enabled, the variant caller will create pileup-based haplotypes in addition to the assembly-based haplotype generation. |
| Tool | ‑‑mitochondria‑mode | No | Mitochondria mode sets emission and initial LODs to 0. |
| Tool | ‑‑tumor‑read‑group‑sm TUMOR_READ_GROUP_SM | No | SM tag for read groups for tumor sample. |
| Tool | ‑‑tumor‑read‑group‑lb TUMOR_READ_GROUP_LB | No | LB tag for read groups for tumor sample. |
| Tool | ‑‑tumor‑read‑group‑pl TUMOR_READ_GROUP_PL | No | PL tag for read groups for tumor sample. |
| Tool | ‑‑tumor‑read‑group‑id‑prefix TUMOR_READ_GROUP_ID_PREFIX | No | Prefix for ID and PU tag for read groups for tumor sample. This prefix will be used for all pair of tumor FASTQ files in this run. The ID and PU tag will consist of this prefix and an identifier which will be unique for a pair of FASTQ files. |
| Tool | ‑‑normal‑read‑group‑sm NORMAL_READ_GROUP_SM | No | SM tag for read groups for normal sample. |
| Tool | ‑‑normal‑read‑group‑lb NORMAL_READ_GROUP_LB | No | LB tag for read groups for normal sample. |
| Tool | ‑‑normal‑read‑group‑pl NORMAL_READ_GROUP_PL | No | PL tag for read groups for normal sample. |
| Tool | ‑‑normal‑read‑group‑id‑prefix NORMAL_READ_GROUP_ID_PREFIX | No | Prefix for ID and PU tags for read groups of a normal sample. This prefix will be used for all pairs of normal FASTQ files in this run. The ID and PU tags will consist of this prefix and an identifier that will be unique for a pair of FASTQ files. |
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
| Performance | ‑‑mutect‑low‑memory | No | Use low memory mode in mutect caller. |
| Performance | ‑‑run‑partition | No | Turn on partition mode; divides genome into multiple partitions and runs 1 process per partition. |
| Performance | ‑‑gpu‑num‑per‑partition GPU_NUM_PER_PARTITION | No | Number of GPUs to use per partition. |
| Performance | ‑‑num‑htvc‑threads NUM_HTVC_THREADS | No | Number of CPU threads per GPU to use. (default: 5) |
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



