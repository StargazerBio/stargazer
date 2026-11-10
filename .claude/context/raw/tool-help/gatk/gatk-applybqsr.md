# gatk ApplyBQSR

```
Using GATK jar /opt/pixi-project/.pixi/envs/default/share/gatk4-4.6.2.0-0/gatk-package-4.6.2.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/pixi-project/.pixi/envs/default/share/gatk4-4.6.2.0-0/gatk-package-4.6.2.0-local.jar ApplyBQSR --help
USAGE: ApplyBQSR [arguments]

Apply a linear base quality recalibration model trained with the BaseRecalibrator tool.
Version:4.6.2.0

Required Arguments:

--bqsr-recal-file,-bqsr Input recalibration table for BQSR  Required. 

--input,-I          BAM/SAM/CRAM file containing reads  This argument must be specified at least once.
                              Required. 

--output,-O         Write output to this file  Required. 

Optional Arguments:

--add-output-sam-program-record 
                              If true, adds a PG tag to created SAM/BAM/CRAM files.  Default value: true. Possible
                              values: {true, false} 

--add-output-vcf-command-line 
                              If true, adds a command line header line to created VCF files.  Default value: true.
                              Possible values: {true, false} 

--allow-missing-read-group 
                              Do not throw an error when encountering a read group not in the recal table  Default
                              value: false. Possible values: {true, false} 

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--cloud-index-prefetch-buffer,-CIPB 
                              Size of the cloud-only prefetch buffer (in MB; 0 to disable). Defaults to
                              cloudPrefetchBuffer if unset.  Default value: -1. 

--cloud-prefetch-buffer,-CPB 
                              Size of the cloud-only prefetch buffer (in MB; 0 to disable).  Default value: 40. 

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

--disable-bam-index-caching,-DBIC 
                              If true, don't cache bam indexes, this will reduce memory requirements but may harm
                              performance if many intervals are specified.  Caching is automatically disabled if there
                              are no intervals specified.  Default value: false. Possible values: {true, false} 

--disable-read-filter,-DF 
                              Read filters to be disabled before analysis  This argument may be specified 0 or more
                              times. Default value: null. Possible values: {WellformedReadFilter} 

--disable-sequence-dictionary-validation 
                              If specified, do not check the sequence dictionaries from our inputs for compatibility.
                              Use at your own risk!  Default value: false. Possible values: {true, false} 

--emit-original-quals 
                              Emit original base qualities under the OQ tag  Default value: false. Possible values:
                              {true, false} 

--exclude-intervals,-XL 
                              One or more genomic intervals to exclude from processing  This argument may be specified 0
                              or more times. Default value: null. 

--gatk-config-file    A configuration file to use with the GATK.  Default value: null. 

--gcs-max-retries,-gcs-retries 
                              If the GCS bucket channel errors out, how many times it will attempt to re-initiate the
                              connection  Default value: 20. 

--gcs-project-for-requester-pays 
                              Project to bill when accessing "requester pays" buckets. If unset, these buckets cannot be
                              accessed.  User must have storage.buckets.get permission on the bucket being accessed. 
                              Default value: . 

--global-qscore-prior Global Qscore Bayesian prior to use for BQSR  Default value: -1.0. 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

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

--max-variants-per-shard 
                              If non-zero, partitions VCF output into shards, each containing up to the given number of
                              records.  Default value: 0. 

--preserve-qscores-less-than 
                              Don't recalibrate bases with quality scores less than this threshold  Default value: 6. 

--quantize-quals     Quantize quality scores to a given number of levels  Default value: 0.  Cannot be used in
                              conjunction with argument(s) staticQuantizationQuals roundDown

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

--reference,-R      Reference sequence  Default value: null. 

--seconds-between-progress-updates 
                              Output traversal statistics every time this many seconds elapse  Default value: 10.0. 

--sequence-dictionary 
                              Use the given sequence dictionary as the master/canonical sequence dictionary.  Must be a
                              .dict file.  Default value: null. 

--sites-only-vcf-output 
                              If true, don't emit genotype fields when writing vcf file output.  Default value: false.
                              Possible values: {true, false} 

--tmp-dir           Temp directory to use.  Default value: null. 

--use-jdk-deflater,-jdk-deflater 
                              Whether to use the JdkDeflater (as opposed to IntelDeflater)  Default value: false.
                              Possible values: {true, false} 

--use-jdk-inflater,-jdk-inflater 
                              Whether to use the JdkInflater (as opposed to IntelInflater)  Default value: false.
                              Possible values: {true, false} 

--use-original-qualities,-OQ 
                              Use the base quality scores from the OQ tag  Default value: false. Possible values: {true,
                              false} 

--verbosity         Control verbosity of logging.  Default value: INFO. Possible values: {ERROR, WARNING,
                              INFO, DEBUG} 

--version            display the version number for this tool  Default value: false. Possible values: {true,
                              false} 

Advanced Arguments:

--disable-tool-default-read-filters 
                              Disable all tool default read filters (WARNING: many tools will not function correctly
                              without their default read filters on)  Default value: false. Possible values: {true,
                              false} 

--round-down-quantized 
                              Round quals down to nearest quantized qual  Default value: false. Possible values: {true,
                              false}  Cannot be used in conjunction with argument(s) quantizationLevels

--showHidden         display hidden arguments  Default value: false. Possible values: {true, false} 

--static-quantized-quals 
                              Use static quantized quality scores to a given number of levels (with -bqsr)  This
                              argument may be specified 0 or more times. Default value: null.  Cannot be used in
                              conjunction with argument(s) quantizationLevels

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
                              Minimum mapping quality to keep (inclusive)  Default value: 10. 

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
