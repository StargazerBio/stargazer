# gatk HaplotypeCaller

```
Using GATK jar /opt/gatk/gatk-package-4.6.1.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/gatk/gatk-package-4.6.1.0-local.jar HaplotypeCaller --help
USAGE: HaplotypeCaller [arguments]

Call germline SNPs and indels via local re-assembly of haplotypes
Version:4.6.1.0

Required Arguments:

--input,-I          BAM/SAM/CRAM file containing reads  This argument must be specified at least once.
                              Required. 

--output,-O         File to which variants should be written  Required. 

--reference,-R      Reference sequence file  Required. 

Optional Arguments:

--add-output-sam-program-record 
                              If true, adds a PG tag to created SAM/BAM/CRAM files.  Default value: true. Possible
                              values: {true, false} 

--add-output-vcf-command-line 
                              If true, adds a command line header line to created VCF files.  Default value: true.
                              Possible values: {true, false} 

--alleles       The set of alleles to force-call regardless of evidence  Default value: null. 

--annotate-with-num-discovered-alleles 
                              If provided, we will annotate records with the number of alternate alleles that were
                              discovered (but not necessarily genotyped) at a given site  Default value: false. Possible
                              values: {true, false} 

--annotation,-A       One or more specific annotations to add to variant calls  This argument may be specified 0
                              or more times. Default value: null. Possible values: {AlleleFraction, AllelePseudoDepth,
                              AS_BaseQualityRankSumTest, AS_FisherStrand, AS_InbreedingCoeff,
                              AS_MappingQualityRankSumTest, AS_QualByDepth, AS_ReadPosRankSumTest, AS_RMSMappingQuality,
                              AS_StrandBiasMutectAnnotation, AS_StrandOddsRatio, AssemblyComplexity, BaseQuality,
                              BaseQualityHistogram, BaseQualityRankSumTest, ChromosomeCounts, ClippingRankSumTest,
                              CountNs, Coverage, CycleSkipStatus, DepthPerAlleleBySample, DepthPerSampleHC, ExcessHet,
                              FisherStrand, FragmentDepthPerAlleleBySample, FragmentLength, GcContent,
                              GenotypeSummaries, HaplotypeFilteringAnnotation, HmerIndelLength, HmerIndelNuc,
                              HmerMotifs, InbreedingCoeff, IndelClassify, IndelLength, LikelihoodRankSumTest,
                              MappingQuality, MappingQualityRankSumTest, MappingQualityZero, OrientationBiasReadCounts,
                              OriginalAlignment, PossibleDeNovo, QualByDepth, RawGtCount, ReadPosition,
                              ReadPosRankSumTest, ReferenceBases, RMSMappingQuality, SampleList, StrandBiasBySample,
                              StrandOddsRatio, TandemRepeat, TransmittedSingleton, UniqueAltReadCount, VariantType} 

--annotation-group,-G One or more groups of annotations to apply to variant calls  This argument may be
                              specified 0 or more times. Default value: null. Possible values:
                              {AlleleSpecificAnnotation, AS_StandardAnnotation, GenotypeAnnotation, InfoFieldAnnotation,
                              JumboGenotypeAnnotation, JumboInfoAnnotation, ReducibleAnnotation, StandardAnnotation,
                              StandardFlowBasedAnnotation, StandardHCAnnotation, StandardMutectAnnotation,
                              VariantAnnotation} 

--annotations-to-exclude,-AX 
                              One or more specific annotations to exclude from variant calls  This argument may be
                              specified 0 or more times. Default value: null. Possible values: {BaseQualityRankSumTest,
                              ChromosomeCounts, Coverage, DepthPerAlleleBySample, DepthPerSampleHC, ExcessHet,
                              FisherStrand, InbreedingCoeff, MappingQualityRankSumTest, QualByDepth, ReadPosRankSumTest,
                              RMSMappingQuality, StrandOddsRatio} 

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--assembly-region-out Output the assembly region to this IGV formatted file  Default value: null. 

--assembly-region-padding 
                              Number of additional bases of context to include around each assembly region  Default
                              value: 100. 

--base-quality-score-threshold 
                              Base qualities below this threshold will be reduced to the minimum (6)  Default value: 18.

--cloud-index-prefetch-buffer,-CIPB 
                              Size of the cloud-only prefetch buffer (in MB; 0 to disable). Defaults to
                              cloudPrefetchBuffer if unset.  Default value: -1. 

--cloud-prefetch-buffer,-CPB 
                              Size of the cloud-only prefetch buffer (in MB; 0 to disable).  Default value: 40. 

--contamination-fraction-to-filter,-contamination 
                              Fraction of contamination in sequencing data (for all samples) to aggressively remove 
                              Default value: 0.0. 

--create-output-bam-index,-OBI 
                              If true, create a BAM/CRAM index when writing a coordinate-sorted BAM/CRAM file.  Default
                              value: true. Possible values: {true, false} 

--create-output-bam-md5,-OBM 
                              If true, create a MD5 digest for any BAM/SAM/CRAM file created  Default value: false.
                              Possible values: {true, false} 

--create-output-variant-index,-OVI 
                              If true, create a VCF index when writing a coordinate-sorted VCF file.  Default value:
                              true. Possible values: {true, false} 

--create-output-variant-md5,-OVM 
                              If true, create a a MD5 digest any VCF file created.  Default value: false. Possible
                              values: {true, false} 

--dbsnp,-D      dbSNP file  Default value: null. 

--disable-bam-index-caching,-DBIC 
                              If true, don't cache bam indexes, this will reduce memory requirements but may harm
                              performance if many intervals are specified.  Caching is automatically disabled if there
                              are no intervals specified.  Default value: false. Possible values: {true, false} 

--disable-read-filter,-DF 
                              Read filters to be disabled before analysis  This argument may be specified 0 or more
                              times. Default value: null. Possible values: {GoodCigarReadFilter, MappedReadFilter,
                              MappingQualityAvailableReadFilter, MappingQualityReadFilter,
                              NonZeroReferenceLengthAlignmentReadFilter, NotDuplicateReadFilter,
                              NotSecondaryAlignmentReadFilter, PassesVendorQualityCheckReadFilter, WellformedReadFilter}

--disable-sequence-dictionary-validation 
                              If specified, do not check the sequence dictionaries from our inputs for compatibility.
                              Use at your own risk!  Default value: false. Possible values: {true, false} 

--dont-use-dragstr-pair-hmm-scores 
                              disable DRAGstr pair-hmm score even when dragstr-params-path was provided  Default value:
                              false. Possible values: {true, false} 

--dont-use-soft-clipped-bases 
                              Do not analyze soft clipped bases in the reads  Default value: false. Possible values:
                              {true, false} 

--dragen-mode        Single argument for enabling the bulk of DRAGEN-GATK features. NOTE: THIS WILL OVERWRITE
                              PROVIDED ARGUMENT CHECK TOOL INFO TO SEE WHICH ARGUMENTS ARE SET).  Default value: false.
                              Possible values: {true, false}  Cannot be used in conjunction with argument(s)
                              dragen378Mode

--dragstr-het-hom-ratio 
                              het to hom prior ratio use with DRAGstr on  Default value: 2. 

--dragstr-params-path 
                              location of the DRAGstr model parameters for STR error correction used in the Pair HMM.
                              When provided, it overrides other PCR error correcting mechanisms  Default value: null. 

--enable-dynamic-read-disqualification-for-genotyping 
                              Will enable less strict read disqualification low base quality reads  Default value:
                              false. Possible values: {true, false} 

--exclude-intervals,-XL 
                              One or more genomic intervals to exclude from processing  This argument may be specified 0
                              or more times. Default value: null. 

--flow-order-for-annotations 
                              flow order used for this annotations. [readGroup:]flowOrder  This argument may be
                              specified 0 or more times. Default value: null. 

--founder-id          Samples representing the population "founders"  This argument may be specified 0 or more
                              times. Default value: null. 

--gatk-config-file    A configuration file to use with the GATK.  Default value: null. 

--gcs-max-retries,-gcs-retries 
                              If the GCS bucket channel errors out, how many times it will attempt to re-initiate the
                              connection  Default value: 20. 

--gcs-project-for-requester-pays 
                              Project to bill when accessing "requester pays" buckets. If unset, these buckets cannot be
                              accessed.  User must have storage.buckets.get permission on the bucket being accessed. 
                              Default value: . 

--genotype-assignment-method,-gam 
                              How we assign genotypes  Default value: USE_PLS_TO_ASSIGN. Possible values:
                              {SET_TO_NO_CALL, USE_PLS_TO_ASSIGN, USE_POSTERIORS_ANNOTATION,
                              SET_TO_NO_CALL_NO_ANNOTATIONS, BEST_MATCH_TO_ORIGINAL, DO_NOT_ASSIGN_GENOTYPES,
                              USE_POSTERIOR_PROBABILITIES, PREFER_PLS} 

--graph-output,-graph Write debug assembly graph information to this file  Default value: null. 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

--heterozygosity      Heterozygosity value used to compute prior probabilities for any locus.  See the GATKDocs
                              for full details on the meaning of this population genetics concept  Default value: 0.001.

--heterozygosity-stdev 
                              Standard deviation of heterozygosity for SNP and indel calling.  Default value: 0.01. 

--indel-heterozygosity 
                              Heterozygosity for indel calling.  See the GATKDocs for heterozygosity for full details on
                              the meaning of this population genetics concept  Default value: 1.25E-4. 

--interval-exclusion-padding,-ixp 
                              Amount of padding (in bp) to add to each interval you are excluding.  Default value: 0. 

--interval-merging-rule,-imr 
                              Interval merging rule for abutting intervals  Default value: ALL. Possible values: {ALL,
                              OVERLAPPING_ONLY} 

--interval-padding,-ip 
                              Amount of padding (in bp) to add to each interval you are including.  Default value: 0. 

--interval-set-rule,-isr 
                              Set merging approach to use for combining interval inputs  Default value: UNION. Possible
                              values: {UNION, INTERSECTION} 

--intervals,-L        One or more genomic intervals over which to operate  This argument may be specified 0 or
                              more times. Default value: null. 

--inverted-read-filter,-XRF 
                              Inverted (with flipped acceptance/failure conditions) read filters applied before analysis
                              (after regular read filters).  This argument may be specified 0 or more times. Default
                              value: null. 

--lenient,-LE        Lenient processing of VCF files  Default value: false. Possible values: {true, false} 

--max-assembly-region-size 
                              Maximum size of an assembly region  Default value: 300. 

--max-reads-per-alignment-start 
                              Maximum number of reads to retain per alignment start position. Reads above this threshold
                              will be downsampled. Set to 0 to disable.  Default value: 50. 

--max-variants-per-shard 
                              If non-zero, partitions VCF output into shards, each containing up to the given number of
                              records.  Default value: 0. 

--min-assembly-region-size 
                              Minimum size of an assembly region  Default value: 50. 

--min-base-quality-score,-mbq 
                              Minimum base quality required to consider a base for calling  Default value: 10. 

--native-pair-hmm-threads 
                              How many threads should a native pairHMM implementation use  Default value: 4. 

--native-pair-hmm-use-double-precision 
                              use double precision in the native pairHmm. This is slower but matches the java
                              implementation better  Default value: false. Possible values: {true, false} 

--num-reference-samples-if-no-call 
                              Number of hom-ref genotypes to infer at sites not present in a panel  Default value: 0. 

--output-mode     Specifies which type of calls we should output  Default value: EMIT_VARIANTS_ONLY.
                              Possible values: {EMIT_VARIANTS_ONLY, EMIT_ALL_CONFIDENT_SITES, EMIT_ALL_ACTIVE_SITES} 

--pedigree,-ped     Pedigree file for determining the population "founders"  Default value: null. 

--ploidy-regions 
                              Interval file with column specifying desired ploidy for genotyping models. Overrides
                              default ploidy and user-provided --ploidy argument in specific regions.  Default value:
                              null. 

--population-callset,-population 
                              Callset to use in calculating genotype priors  Default value: null. 

--QUIET              Whether to suppress job-summary info on System.err.  Default value: false. Possible
                              values: {true, false} 

--read-filter,-RF     Read filters to be applied before analysis  This argument may be specified 0 or more
                              times. Default value: null. Possible values: {AlignmentAgreesWithHeaderReadFilter,
                              AllowAllReadsReadFilter, AmbiguousBaseReadFilter, CigarContainsNoNOperator,
                              ExcessiveEndClippedReadFilter, FirstOfPairReadFilter,
                              FlowBasedTPAttributeSymetricReadFilter, FlowBasedTPAttributeValidReadFilter,
                              FragmentLengthReadFilter, GoodCigarReadFilter, HasReadGroupReadFilter,
                              HmerQualitySymetricReadFilter, IntervalOverlapReadFilter,
                              JexlExpressionReadTagValueFilter, LibraryReadFilter, MappedReadFilter,
                              MappingQualityAvailableReadFilter, MappingQualityNotZeroReadFilter,
                              MappingQualityReadFilter, MatchingBasesAndQualsReadFilter, MateDifferentStrandReadFilter,
                              MateDistantReadFilter, MateOnSameContigOrNoMappedMateReadFilter,
                              MateUnmappedAndUnmappedReadFilter, MetricsReadFilter,
                              NonChimericOriginalAlignmentReadFilter, NonZeroFragmentLengthReadFilter,
                              NonZeroReferenceLengthAlignmentReadFilter, NotDuplicateReadFilter,
                              NotOpticalDuplicateReadFilter, NotProperlyPairedReadFilter,
                              NotSecondaryAlignmentReadFilter, NotSupplementaryAlignmentReadFilter,
                              OverclippedReadFilter, PairedReadFilter, PassesVendorQualityCheckReadFilter,
                              PlatformReadFilter, PlatformUnitReadFilter, PrimaryLineReadFilter,
                              ProperlyPairedReadFilter, ReadGroupBlackListReadFilter, ReadGroupHasFlowOrderReadFilter,
                              ReadGroupReadFilter, ReadLengthEqualsCigarLengthReadFilter, ReadLengthReadFilter,
                              ReadNameReadFilter, ReadStrandFilter, ReadTagValueFilter, SampleReadFilter,
                              SecondOfPairReadFilter, SeqIsStoredReadFilter, SoftClippedReadFilter,
                              ValidAlignmentEndReadFilter, ValidAlignmentStartReadFilter, WellformedFlowBasedReadFilter,
                              WellformedReadFilter} 

--read-index        Indices to use for the read inputs. If specified, an index must be provided for every read
                              input and in the same order as the read inputs. If this argument is not specified, the
                              path to the index for each input will be inferred automatically.  This argument may be
                              specified 0 or more times. Default value: null. 

--read-validation-stringency,-VS 
                              Validation stringency for all SAM/BAM/CRAM/SRA files read by this program.  The default
                              stringency value SILENT can improve performance when processing a BAM file in which
                              variable-length data (read, qualities, tags) do not otherwise need to be decoded.  Default
                              value: SILENT. Possible values: {STRICT, LENIENT, SILENT} 

--recover-dangling-heads 
                              This argument is DEPRECATED (This feature is deprecated and will be removed in a future
                              release.). This argument is deprecated since version 3.3  Default value: false. Possible
                              values: {true, false} 

--sample-name,-ALIAS  Name of single sample to use from a multi-sample bam  Default value: null. 

--sample-ploidy,-ploidy 
                              Ploidy (number of chromosomes) per sample. For pooled data, set to (Number of samples in
                              each pool * Sample Ploidy).  Default value: 2. 

--seconds-between-progress-updates 
                              Output traversal statistics every time this many seconds elapse  Default value: 10.0. 

--sequence-dictionary 
                              Use the given sequence dictionary as the master/canonical sequence dictionary.  Must be a
                              .dict file.  Default value: null. 

--sites-only-vcf-output 
                              If true, don't emit genotype fields when writing vcf file output.  Default value: false.
                              Possible values: {true, false} 

--standard-min-confidence-threshold-for-calling,-stand-call-conf 
                              The minimum phred-scaled confidence threshold at which variants should be called  Default
                              value: 30.0. 

--tmp-dir           Temp directory to use.  Default value: null. 

--use-jdk-deflater,-jdk-deflater 
                              Whether to use the JdkDeflater (as opposed to IntelDeflater)  Default value: false.
                              Possible values: {true, false} 

--use-jdk-inflater,-jdk-inflater 
                              Whether to use the JdkInflater (as opposed to IntelInflater)  Default value: false.
                              Possible values: {true, false} 

--use-new-qual-calculator,-new-qual 
                              This argument is DEPRECATED (New qual score is on by default). Use the new AF model
                              instead of the so-called exact model  Default value: true. Possible values: {true, false} 

--use-pdhmm          Partially Determined HMM, an alternative to the regular assembly haplotypes where we
                              instead construct artificial haplotypes out of the union of the assembly and pileup
                              alleles.  Default value: false. Possible values: {true, false} 

--use-posteriors-to-calculate-qual,-gp-qual 
                              if available, use the genotype posterior probabilities to calculate the site QUAL  Default
                              value: false. Possible values: {true, false} 

--verbosity         Control verbosity of logging.  Default value: INFO. Possible values: {ERROR, WARNING,
                              INFO, DEBUG} 

--version            display the version number for this tool  Default value: false. Possible values: {true,
                              false} 

Advanced Arguments:

--active-probability-threshold 
                              Minimum probability for a locus to be considered active.  Default value: 0.002. 

--adaptive-pruning   Use Mutect2's adaptive graph pruning algorithm  Default value: false. Possible values:
                              {true, false} 

--adaptive-pruning-initial-error-rate 
                              Initial base error rate estimate for adaptive pruning  Default value: 0.001. 

--all-site-pls       Annotate all sites with PLs  Default value: false. Possible values: {true, false} 

--allele-informative-reads-overlap-margin 
                              Likelihood and read-based annotations will only take into consideration reads that overlap
                              the variant or any base no further than this distance expressed in base pairs  Default
                              value: 2. 

--allow-non-unique-kmers-in-ref 
                              Allow graphs that have non-unique kmers in the reference  Default value: false. Possible
                              values: {true, false} 

--apply-bqd          If enabled this argument will apply the DRAGEN-GATK BaseQualityDropout model to the
                              genotyping model for filtering sites due to Linked Error mode.  Default value: false.
                              Possible values: {true, false} 

--apply-frd          If enabled this argument will apply the DRAGEN-GATK ForeignReadDetection model to the
                              genotyping model for filtering sites.  Default value: false. Possible values: {true,
                              false} 

--bam-output,-bamout  File to which assembled haplotypes should be written  Default value: null. 

--bam-writer-type Which haplotypes should be written to the BAM  Default value: CALLED_HAPLOTYPES. Possible
                              values: {ALL_POSSIBLE_HAPLOTYPES, CALLED_HAPLOTYPES, NO_HAPLOTYPES,
                              CALLED_HAPLOTYPES_NO_READS} 

--comparison,-comp 
                              Comparison VCF file(s)  This argument may be specified 0 or more times. Default value:
                              null. 

--contamination-fraction-per-sample-file,-contamination-file 
                              Tab-separated File containing fraction of contamination in sequencing data (per sample) to
                              aggressively remove. Format should be "" (Contamination is
                              double) per line; No header.  Default value: null. 

--debug-assembly,-debug 
                              Print out verbose debug information about each assembly region  Default value: false.
                              Possible values: {true, false} 

--disable-cap-base-qualities-to-map-quality 
                              If false this disables capping of base qualities in the HMM to the mapping quality of the
                              read  Default value: false. Possible values: {true, false} 

--disable-optimizations 
                              Don't skip calculations in ActiveRegions with no variants  Default value: false. Possible
                              values: {true, false} 

--disable-spanning-event-genotyping 
                              If enabled this argument will disable inclusion of the '*' spanning event when genotyping
                              events that overlap deletions  Default value: false. Possible values: {true, false} 

--disable-symmetric-hmm-normalizing 
                              Toggle to revive legacy behavior of asymmetrically normalizing the arguments to the
                              reference haplotype  Default value: false. Possible values: {true, false} 

--disable-tool-default-annotations 
                              Disable all tool default annotations  Default value: false. Possible values: {true, false}

--disable-tool-default-read-filters 
                              Disable all tool default read filters (WARNING: many tools will not function correctly
                              without their default read filters on)  Default value: false. Possible values: {true,
                              false} 

--do-not-correct-overlapping-quality 
                              Disable overlapping base quality correction  Default value: false. Possible values: {true,
                              false} 

--do-not-run-physical-phasing 
                              Disable physical phasing  Default value: false. Possible values: {true, false} 

--dont-increase-kmer-sizes-for-cycles 
                              Disable iterating over kmer sizes when graph cycles are detected  Default value: false.
                              Possible values: {true, false} 

--dont-use-dragstr-priors 
                              Forfeit the use of the DRAGstr model to calculate genotype priors. This argument does not
                              have any effect in the absence of DRAGstr model parameters (--dragstr-model-params) 
                              Default value: false. Possible values: {true, false} 

--dragen-378-concordance-mode 
                              Single argument for enabling the bulk of DRAGEN-GATK features including new developments
                              for concordance against DRAGEN 3.7.8. NOTE: THIS WILL OVERWRITE PROVIDED ARGUMENT CHECK
                              TOOL INFO TO SEE WHICH ARGUMENTS ARE SET).  Default value: false. Possible values: {true,
                              false}  Cannot be used in conjunction with argument(s) dragen3412mode

--emit-ref-confidence,-ERC 
                              Mode for emitting reference confidence scores (For Mutect2, this is a BETA feature) 
                              Default value: NONE. Possible values: {NONE, BP_RESOLUTION, GVCF} 

--enable-all-annotations 
                              Use all possible annotations (not for the faint of heart)  Default value: false. Possible
                              values: {true, false} 

--expected-mismatch-rate-for-read-disqualification 
                              Error rate used to set expectation for post HMM read disqualification based on mismatches 
                              Default value: 0.02. 

--floor-blocks       Output the band lower bound for each GQ block regardless of the data it represents 
                              Default value: false. Possible values: {true, false} 

--flow-assembly-collapse-partial-mode 
                              Collapse long flow-based hmers only up to difference in reference  Default value: false.
                              Possible values: {true, false} 

--flow-disallow-probs-larger-than-call 
                              Cap probabilities of error to 1 relative to base call  Default value: false. Possible
                              values: {true, false} 

--flow-fill-empty-bins-value 
                              Value to fill the zeros of the matrix with  Default value: 0.001. 

--flow-filter-alleles 
                              pre-filter alleles before genotyping  Default value: false. Possible values: {true, false}

--flow-filter-alleles-qual-threshold 
                              Threshold for prefiltering alleles on quality  Default value: 30.0. 

--flow-filter-alleles-sor-threshold 
                              Threshold for prefiltering alleles on SOR  Default value: 3.0. 

--flow-filter-lone-alleles 
                              Remove also lone alleles during allele filtering  Default value: false. Possible values:
                              {true, false} 

--flow-lump-probs    Should all probabilities of insertion or deletion in the flow be combined together 
                              Default value: false. Possible values: {true, false} 

--flow-matrix-mods    Modifications instructions to the read flow matrix. Format is src,dst{,src,dst}+. Example:
                              10,12,11,12 - these instructions will copy element 10 into 11 and 12  Default value: null.

--flow-mode         Single argument for enabling the bulk of Flow Based features. NOTE: THIS WILL OVERWRITE
                              PROVIDED ARGUMENT CHECK TOOL INFO TO SEE WHICH ARGUMENTS ARE SET).  Default value: NONE.
                              Possible values: {NONE, STANDARD, ADVANCED} 

--flow-probability-scaling-factor 
                              probability scaling factor for (phred=10) for probability quantization  Default value: 10.

--flow-quantization-bins 
                              Number of bins for probability quantization  Default value: 121. 

--flow-remove-non-single-base-pair-indels 
                              Should the probabilities of more then 1 indel be used  Default value: false. Possible
                              values: {true, false} 

--flow-remove-one-zero-probs 
                              Remove probabilities of basecall of zero from non-zero genome  Default value: false.
                              Possible values: {true, false} 

--flow-report-insertion-or-deletion 
                              Report either insertion or deletion, probability, not both  Default value: false. Possible
                              values: {true, false} 

--flow-retain-max-n-probs-base-format 
                              Keep only hmer/2 probabilities (like in base format)  Default value: false. Possible
                              values: {true, false} 

--flow-symmetric-indel-probs 
                              Should indel probabilities be symmetric in flow  Default value: false. Possible values:
                              {true, false} 

--flow-use-t0-tag    Use t0 tag if exists in the read to create flow matrix  Default value: false. Possible
                              values: {true, false} 

--force-active       If provided, all regions will be marked as active  Default value: false. Possible values:
                              {true, false} 

--force-call-filtered-alleles,-genotype-filtered-alleles 
                              Force-call filtered alleles included in the resource specified by --alleles  Default
                              value: false. Possible values: {true, false} 

--gvcf-gq-bands,-GQB Exclusive upper bounds for reference confidence GQ bands (must be in [1, 100] and
                              specified in increasing order)  This argument may be specified 0 or more times. Default
                              value: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                              24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
                              46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 70, 80, 90, 99]. 

--indel-size-to-eliminate-in-ref-model 
                              The size of an indel to check for in the reference model  Default value: 10. 

--keep-boundary-flows 
                              prevent spreading of boundary flows.  Default value: false. Possible values: {true, false}

--kmer-size          Kmer size to use in the read threading assembler  This argument may be specified 0 or more
                              times. Default value: [10, 25]. 

--likelihood-calculation-engine 
                              What likelihood calculation engine to use to calculate the relative likelihood of reads vs
                              haplotypes  Default value: PairHMM. Possible values: {PairHMM, FlowBased, FlowBasedHMM} 

--linked-de-bruijn-graph 
                              If enabled, the Assembly Engine will construct a Linked De Bruijn graph to recover better
                              haplotypes  Default value: false. Possible values: {true, false} 

--mapping-quality-threshold-for-genotyping 
                              Control the threshold for discounting reads from the genotyper due to mapping quality
                              after the active region detection and assembly steps but before genotyping. NOTE: this is
                              in contrast to the --minimum-mapping-quality argument which filters reads from all parts
                              of the HaplotypeCaller. If you would like to call genotypes with a different threshold
                              both arguments must be set.  Default value: 20. 

--max-alternate-alleles 
                              Maximum number of alternate alleles to genotype  Default value: 6. 

--max-effective-depth-adjustment-for-frd 
                              Set the maximum depth to modify FRD adjustment to in the event of high depth sites (0 to
                              disable)  Default value: 0. 

--max-genotype-count Maximum number of genotypes to consider at any site  Default value: 1024. 

--max-mnp-distance,-mnp-dist 
                              Two or more phased substitutions separated by this distance or less are merged into MNPs. 
                              Default value: 0. 

--max-num-haplotypes-in-population 
                              Maximum number of haplotypes to consider for your population  Default value: 128. 

--max-prob-propagation-distance 
                              Upper limit on how many bases away probability mass can be moved around when calculating
                              the boundaries between active and inactive assembly regions  Default value: 50. 

--max-unpruned-variants 
                              Maximum number of variants in graph the adaptive pruner will allow  Default value: 100. 

--min-dangling-branch-length 
                              Minimum length of a dangling branch to attempt recovery  Default value: 4. 

--min-pruning        Minimum support to not prune paths in the graph  Default value: 2. 

--num-pruning-samples 
                              Number of samples that must pass the minPruning threshold  Default value: 1. 

--pair-hmm-gap-continuation-penalty 
                              Flat gap continuation penalty for use in the Pair HMM  Default value: 10. 

--pair-hmm-implementation,-pairHMM 
                              The PairHMM implementation to use for genotype likelihood calculations  Default value:
                              FASTEST_AVAILABLE. Possible values: {EXACT, ORIGINAL, LOGLESS_CACHING,
                              AVX_LOGLESS_CACHING, AVX_LOGLESS_CACHING_OMP, FASTEST_AVAILABLE} 

--pair-hmm-results-file 
                              File to write exact pairHMM inputs/outputs to for debugging purposes  Default value: null.

--pcr-indel-model 
                              The PCR indel model to use  Default value: CONSERVATIVE. Possible values: {NONE, HOSTILE,
                              AGGRESSIVE, CONSERVATIVE} 

--phred-scaled-global-read-mismapping-rate 
                              The global assumed mismapping rate for reads  Default value: 45. 

--pileup-detection   If enabled, the variant caller will create pileup-based haplotypes in addition to the
                              assembly-based haplotype generation.  Default value: false. Possible values: {true, false}

--pruning-lod-threshold 
                              Ln likelihood ratio threshold for adaptive pruning algorithm  Default value:
                              2.302585092994046. 

--pruning-seeding-lod-threshold 
                              Ln likelihood ratio threshold for seeding subgraph of good variation in adaptive pruning
                              algorithm  Default value: 9.210340371976184. 

--recover-all-dangling-branches 
                              Recover all dangling branches  Default value: false. Possible values: {true, false} 

--reference-model-deletion-quality 
                              The quality of deletion in the reference model  Default value: 30. 

--showHidden         display hidden arguments  Default value: false. Possible values: {true, false} 

--smith-waterman 
                              Which Smith-Waterman implementation to use, generally FASTEST_AVAILABLE is the right
                              choice  Default value: FASTEST_AVAILABLE. Possible values: {FASTEST_AVAILABLE,
                              AVX_ENABLED, JAVA} 

--smith-waterman-dangling-end-gap-extend-penalty 
                              Smith-Waterman gap-extend penalty for dangling-end recovery.  Default value: -6. 

--smith-waterman-dangling-end-gap-open-penalty 
                              Smith-Waterman gap-open penalty for dangling-end recovery.  Default value: -110. 

--smith-waterman-dangling-end-match-value 
                              Smith-Waterman match value for dangling-end recovery.  Default value: 25. 

--smith-waterman-dangling-end-mismatch-penalty 
                              Smith-Waterman mismatch penalty for dangling-end recovery.  Default value: -50. 

--smith-waterman-haplotype-to-reference-gap-extend-penalty 
                              Smith-Waterman gap-extend penalty for haplotype-to-reference alignment.  Default value:
                              -11. 

--smith-waterman-haplotype-to-reference-gap-open-penalty 
                              Smith-Waterman gap-open penalty for haplotype-to-reference alignment.  Default value:
                              -260. 

--smith-waterman-haplotype-to-reference-match-value 
                              Smith-Waterman match value for haplotype-to-reference alignment.  Default value: 200. 

--smith-waterman-haplotype-to-reference-mismatch-penalty 
                              Smith-Waterman mismatch penalty for haplotype-to-reference alignment.  Default value:
                              -150. 

--smith-waterman-read-to-haplotype-gap-extend-penalty 
                              Smith-Waterman gap-extend penalty for read-to-haplotype alignment.  Default value: -5. 

--smith-waterman-read-to-haplotype-gap-open-penalty 
                              Smith-Waterman gap-open penalty for read-to-haplotype alignment.  Default value: -30. 

--smith-waterman-read-to-haplotype-match-value 
                              Smith-Waterman match value for read-to-haplotype alignment.  Default value: 10. 

--smith-waterman-read-to-haplotype-mismatch-penalty 
                              Smith-Waterman mismatch penalty for read-to-haplotype alignment.  Default value: -15. 

--soft-clip-low-quality-ends 
                              If enabled will preserve low-quality read ends as softclips (used for DRAGEN-GATK BQD
                              genotyper model)  Default value: false. Possible values: {true, false} 

--transform-dragen-mapping-quality 
                              If enabled this argument will map DRAGEN aligner aligned reads with mapping quality <=250
                              to scale up to MQ 50  Default value: false. Possible values: {true, false} 

--use-filtered-reads-for-annotations 
                              Use the contamination-filtered read maps for the purposes of annotating variants  Default
                              value: false. Possible values: {true, false} 

--use-pdhmm-overlap-optimization 
                              PDHMM: An optimization to PDHMM, if set this will skip running PDHMM haplotype
                              determination on reads that don't overlap (within a few bases) of the determined allele in
                              each haplotype. This substantially reduces the amount of read-haplotype comparisons at the
                              expense of ignoring read realignment mapping artifacts. (Requires '--use-pdhmm' argument) 
                              Default value: false. Possible values: {true, false} 

Conditional Arguments for annotation:

Valid only if "AllelePseudoDepth" is specified:
--dirichlet-keep-prior-in-count 
                              By default we don't keep the prior use in the output counts ase it makes it easier to
                              interpretthis quantity as the number of supporting reads specially in low depth sites. We
                              this toggled the prior is included  Default value: false. Possible values: {true, false} 

--dirichlet-prior-pseudo-count 
                              Pseudo-count used as prior for all alleles. The default is 1.0 resulting in a flat prior 
                              Default value: 1.0. 

--pseudo-count-weight-decay-rate 
                              A what rate the weight of a read decreases base on its informativeness; e.g. 1.0 is linear
                              decay (default), 2.0 is for quadratic decay  Default value: 1.0. 

Valid only if "AssemblyComplexity" is specified:
--assembly-complexity-reference-mode 
                              If enabled will treat the reference as the basis for assembly complexity as opposed to
                              estimated germline haplotypes  Default value: false. Possible values: {true, false} 

Valid only if "PossibleDeNovo" is specified:
--denovo-depth-threshold 
                              Minimum depth (DP) for all trio members to be considered for de novo calculation.  Default
                              value: 0. 

--denovo-parent-gq-threshold 
                              Minimum genotype quality for parents to be considered for de novo calculation (separate
                              from GQ thershold for full trio).  Default value: 20. 

Valid only if "RMSMappingQuality" is specified:
--allow-old-rms-mapping-quality-annotation-data 
                              Override to allow old RMSMappingQuality annotated VCFs to function  Default value: false.
                              Possible values: {true, false} 

Conditional Arguments for readFilter:

Valid only if "AmbiguousBaseReadFilter" is specified:
--ambig-filter-bases Threshold number of ambiguous bases. If null, uses threshold fraction; otherwise,
                              overrides threshold fraction.  Default value: null.  Cannot be used in conjunction with
                              argument(s) maxAmbiguousBaseFraction

--ambig-filter-frac   Threshold fraction of ambiguous bases  Default value: 0.05.  Cannot be used in conjunction
                              with argument(s) maxAmbiguousBases

Valid only if "ExcessiveEndClippedReadFilter" is specified:
--max-clipped-bases  Maximum number of clipped bases on either end of a given read  Default value: 1000. 

Valid only if "FlowBasedTPAttributeValidReadFilter" is specified:
--read-filter-max-hmer 
                              maxHmer to use for testing in the filter  Default value: 12. 

Valid only if "FragmentLengthReadFilter" is specified:
--max-fragment-length 
                              Maximum length of fragment (insert size)  Default value: 1000000. 

--min-fragment-length 
                              Minimum length of fragment (insert size)  Default value: 0. 

Valid only if "IntervalOverlapReadFilter" is specified:
--keep-intervals      One or more genomic intervals to keep  This argument must be specified at least once.
                              Required. 

Valid only if "JexlExpressionReadTagValueFilter" is specified:
--read-filter-expression 
                              One or more JEXL expressions used to filter  This argument must be specified at least
                              once. Required. 

Valid only if "LibraryReadFilter" is specified:
--library             Name of the library to keep  This argument must be specified at least once. Required. 

Valid only if "MappingQualityReadFilter" is specified:
--maximum-mapping-quality 
                              Maximum mapping quality to keep (inclusive)  Default value: null. 

--minimum-mapping-quality 
                              Minimum mapping quality to keep (inclusive)  Default value: 20. 

Valid only if "MateDistantReadFilter" is specified:
--mate-too-distant-length 
                              Minimum start location difference at which mapped mates are considered distant  Default
                              value: 1000. 

Valid only if "OverclippedReadFilter" is specified:
--dont-require-soft-clips-both-ends 
                              Allow a read to be filtered out based on having only 1 soft-clipped block. By default,
                              both ends must have a soft-clipped block, setting this flag requires only 1 soft-clipped
                              block  Default value: false. Possible values: {true, false} 

--filter-too-short   Minimum number of aligned bases  Default value: 30. 

Valid only if "PlatformReadFilter" is specified:
--platform-filter-name 
                              Platform attribute (PL) to match  This argument must be specified at least once. Required.

Valid only if "PlatformUnitReadFilter" is specified:
--black-listed-lanes  Platform unit (PU) to filter out  This argument must be specified at least once. Required.

Valid only if "ReadGroupBlackListReadFilter" is specified:
--read-group-black-list 
                              A read group filter expression in the form "attribute:value", where "attribute" is a two
                              character read group attribute such as "RG" or "PU".  This argument must be specified at
                              least once. Required. 

Valid only if "ReadGroupReadFilter" is specified:
--keep-read-group     The name of the read group to keep  Required. 

Valid only if "ReadLengthReadFilter" is specified:
--max-read-length    Keep only reads with length at most equal to the specified value  Required. 

--min-read-length    Keep only reads with length at least equal to the specified value  Default value: 1. 

Valid only if "ReadNameReadFilter" is specified:
--read-name           Keep only reads with this read name  This argument must be specified at least once.
                              Required. 

Valid only if "ReadStrandFilter" is specified:
--keep-reverse-strand-only 
                              Keep only reads on the reverse strand  Required. Possible values: {true, false} 

Valid only if "ReadTagValueFilter" is specified:
--read-filter-tag     Look for this tag in read  Required. 

--read-filter-tag-comp Compare value in tag to this value  Default value: 0.0. 

--read-filter-tag-op 
                              Compare value in tag to value with this operator. If T is the value in the tag, OP is the
                              operation provided, and V is the value in read-filter-tag, then the read will pass the
                              filter iff T OP V is true.  Default value: EQUAL. Possible values: {LESS, LESS_OR_EQUAL,
                              GREATER, GREATER_OR_EQUAL, EQUAL, NOT_EQUAL} 

Valid only if "SampleReadFilter" is specified:
--sample              The name of the sample(s) to keep, filtering out all others  This argument must be
                              specified at least once. Required. 

Valid only if "SoftClippedReadFilter" is specified:
--max-soft-clipped-leading-trailing-ratio 
                              Threshold ratio of soft clipped bases (leading / trailing the cigar string) to total bases
                              in read for read to be filtered.  Default value: null.  Cannot be used in conjunction with
                              argument(s) maximumSoftClippedRatio

--max-soft-clipped-ratio 
                              Threshold ratio of soft clipped bases (anywhere in the cigar string) to total bases in
                              read for read to be filtered.  Default value: null.  Cannot be used in conjunction with
                              argument(s) maximumLeadingTrailingSoftClippedRatio

Tool returned:
0
```
