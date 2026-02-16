# gatk MarkDuplicates 

```
Using GATK jar /opt/gatk/gatk-package-4.6.1.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/gatk/gatk-package-4.6.1.0-local.jar MarkDuplicates --help
USAGE: MarkDuplicates [arguments]

Identifies duplicate reads.  
This tool locates and tags duplicate reads in a SAM, BAM or CRAM file, where duplicate
reads are defined as originating from a single fragment of DNA.  Duplicates can arise during sample preparation e.g.
library construction using PCR.  See also <a
href='https://broadinstitute.github.io/picard/command-line-overview.html#EstimateLibraryComplexity'>EstimateLibraryComplexity
for additional notes on PCR duplication artifacts.  Duplicate reads can also result from a single amplification cluster,
incorrectly detected as multiple clusters by the optical sensor of the sequencing instrument.  These duplication
artifacts are referred to as optical duplicates.
The MarkDuplicates tool works by comparing sequences in the 5
prime positions of both reads and read-pairs in a SAM/BAM file.  A BARCODE_TAG option is available to facilitate
duplicate marking using molecular barcodes.  After duplicate reads are collected, the tool differentiates the primary
and duplicate reads using an algorithm that ranks reads by the sums of their base-quality scores (default method). Note
that this is different from directly checking if the sequences match, which MarkDuplicates does not do.  
The
tool's main output is a new SAM, BAM or CRAM file, in which duplicates have been identified in the SAM flags field for
each read.  Duplicates are marked with the hexadecimal value of 0x0400, which corresponds to a decimal value of 1024. 
If you are not familiar with this type of annotation, please see the following <a
href='https://www.broadinstitute.org/gatk/blog?id=7019'>blog post for additional information.
Although the
bitwise flag annotation indicates whether a read was marked as a duplicate, it does not identify the type of duplicate. 
To do this, a new tag called the duplicate type (DT) tag was recently added as an optional output in  the 'optional
field' section of a SAM/BAM/CRAM file.  Invoking the TAGGING_POLICY option, you can instruct the program to mark all the
duplicates (All), only the optical duplicates (OpticalOnly), or no duplicates (DontTag).  The records within the output
of a SAM/BAM/CRAM file will have values for the 'DT' tag (depending on the invoked TAGGING_POLICY), as either
library/PCR-generated duplicates (LB), or sequencing-platform artifact duplicates (SQ).  This tool uses the
READ_NAME_REGEX and the OPTICAL_DUPLICATE_PIXEL_DISTANCE options as the primary methods to identify and differentiate
duplicate types.  Set READ_NAME_REGEX to null to skip optical duplicate detection, e.g. for RNA-seq or other data where
duplicate sets are extremely large and estimating library complexity is not an aim.  Note that without optical duplicate
counts, library size estimation will be inaccurate. 
MarkDuplicates also produces a metrics file indicating the
numbers of duplicates for both single- and paired-end reads.  
The program can take either coordinate-sorted or
query-sorted inputs, however the behavior is slightly different.  When the input is coordinate-sorted, unmapped mates of
mapped records and supplementary/secondary alignments are not marked as duplicates.  However, when the input is
query-sorted (actually query-grouped), then unmapped mates and secondary/supplementary reads are not excluded from the
duplication test and can be marked as duplicate reads.  
If desired, duplicates can be removed using the
REMOVE_DUPLICATE and REMOVE_SEQUENCING_DUPLICATES options.
## Usage example:

```
java -jar picard.jar
MarkDuplicates \      I=input.bam \      O=marked_duplicates.bam \     
M=marked_dup_metrics.txt
```
Please see <a
href='http://broadinstitute.github.io/picard/picard-metric-definitions.html#DuplicationMetrics'>MarkDuplicates for
detailed explanations of the output metrics.
Version:4.6.1.0

Required Arguments:

--INPUT,-I            One or more input SAM, BAM or CRAM files to analyze. Must be coordinate sorted.  This
                              argument must be specified at least once. Required. 

--METRICS_FILE,-M       File to write duplication metrics to  Required. 

--OUTPUT,-O             The output file to write marked records to  Required. 

Optional Arguments:

--ADD_PG_TAG_TO_READS 
                              Add PG tag to each read in a SAM or BAM  Default value: true. Possible values: {true,
                              false} 

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--ASSUME_SORT_ORDER,-ASO 
                              If not null, assume that the input file has this order even if the header says otherwise. 
                              Default value: null. Possible values: {unsorted, queryname, coordinate, duplicate,
                              unknown}  Cannot be used in conjunction with argument(s) ASSUME_SORTED (AS)

--ASSUME_SORTED,-AS  If true, assume that the input file is coordinate sorted even if the header says
                              otherwise. Deprecated, used ASSUME_SORT_ORDER=coordinate instead.  Default value: false.
                              Possible values: {true, false}  Cannot be used in conjunction with argument(s)
                              ASSUME_SORT_ORDER (ASO)

--BARCODE_TAG         Barcode SAM tag (ex. BC for 10X Genomics)  Default value: null. 

--CLEAR_DT           Clear DT tag from input SAM records. Should be set to false if input SAM doesn't have this
                              tag.  Default true  Default value: true. Possible values: {true, false} 

--COMMENT,-CO         Comment(s) to include in the output file's header.  This argument may be specified 0 or
                              more times. Default value: null. 

--COMPRESSION_LEVEL  Compression level for all compressed files created (e.g. BAM and VCF).  Default value: 2. 

--CREATE_INDEX       Whether to create an index when writing VCF or coordinate sorted BAM output.  Default
                              value: false. Possible values: {true, false} 

--CREATE_MD5_FILE    Whether to create an MD5 digest for any BAM or FASTQ files created.    Default value:
                              false. Possible values: {true, false} 

--DUPLEX_UMI         Treat UMIs as being duplex stranded.  This option requires that the UMI consist of two
                              equal length strings that are separated by a hyphen (e.g. 'ATC-GTC'). Reads are considered
                              duplicates if, in addition to standard definition, have identical normalized UMIs.  A UMI
                              from the 'bottom' strand is normalized by swapping its content around the hyphen (eg.
                              ATC-GTC becomes GTC-ATC).  A UMI from the 'top' strand is already normalized as it is.
                              Both reads from a read pair considered top strand if the read 1 unclipped 5' coordinate is
                              less than the read 2 unclipped 5' coordinate. All chimeric reads and read fragments are
                              treated as having come from the top strand. With this option is it required that the
                              BARCODE_TAG hold non-normalized UMIs. Default false.  Default value: false. Possible
                              values: {true, false} 

--DUPLICATE_SCORING_STRATEGY,-DS 
                              The scoring strategy for choosing the non-duplicate among candidates.  Default value:
                              SUM_OF_BASE_QUALITIES. Possible values: {SUM_OF_BASE_QUALITIES,
                              TOTAL_MAPPED_REFERENCE_LENGTH, RANDOM} 

--FLOW_DUP_STRATEGY 
                              Use specific quality summing strategy for flow based reads. Two strategies are available:
                              FLOW_QUALITY_SUM_STRATEG: The selects the read with the best total homopolymer quality.
                              FLOW_END_QUALITY_STRATEGY: The strategy selects the read with the best homopolymer quality
                              close to the end (10 bases) of the read.  The latter strategy is recommended for samples
                              with high duplication rate   Default value: FLOW_QUALITY_SUM_STRATEGY. Possible values:
                              {FLOW_QUALITY_SUM_STRATEGY, FLOW_END_QUALITY_STRATEGY} 

--FLOW_EFFECTIVE_QUALITY_THRESHOLD 
                              Threshold for considering a quality value high enough to be included when calculating
                              FLOW_QUALITY_SUM_STRATEGY calculation.  Default value: 15. 

--FLOW_MODE          enable parameters and behavior specific to flow based reads.  Default value: false.
                              Possible values: {true, false} 

--FLOW_Q_IS_KNOWN_END 
                              Treat position of read trimming based on quality as the known end (relevant for flow based
                              reads). Default false - if the read is trimmed on quality its end is not defined and the
                              read is duplicate of any read starting at the same place.  Default value: false. Possible
                              values: {true, false} 

--FLOW_SKIP_FIRST_N_FLOWS 
                              Skip first N flows, starting from the read's start, when considering duplicates. Useful
                              for flow based reads where sometimes there is noise in the first flows (for this argument,
                              "read start" means 5' end).  Default value: 0. 

--FLOW_UNPAIRED_END_UNCERTAINTY 
                              Maximal difference of the read end position that counted as equal. Useful for flow based
                              reads where the end position might vary due to sequencing errors. (for this argument,
                              "read end" means 3' end)  Default value: 0. 

--FLOW_UNPAIRED_START_UNCERTAINTY 
                              Maximal difference of the read start position that counted as equal. Useful for flow based
                              reads where the end position might vary due to sequencing errors. (for this argument,
                              "read start" means 5' end in the direction of sequencing)  Default value: 0. 

--FLOW_USE_END_IN_UNPAIRED_READS 
                              Make the end location of single end read be significant when considering duplicates, in
                              addition to the start location, which is always significant (i.e. require single-ended
                              reads to start andend on the same position to be considered duplicate) (for this argument,
                              "read end" means 3' end).  Default value: false. Possible values: {true, false} 

--FLOW_USE_UNPAIRED_CLIPPED_END 
                              Use position of the clipping as the end position, when considering duplicates (or use the
                              unclipped end position) (for this argument, "read end" means 3' end).  Default value:
                              false. Possible values: {true, false} 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

--MAX_FILE_HANDLES_FOR_READ_ENDS_MAP,-MAX_FILE_HANDLES 
                              Maximum number of file handles to keep open when spilling read ends to disk. Set this
                              number a little lower than the per-process maximum number of file that may be open. This
                              number can be found by executing the 'ulimit -n' command on a Unix system.  Default value:
                              8000. 

--MAX_OPTICAL_DUPLICATE_SET_SIZE 
                              This number is the maximum size of a set of duplicate reads for which we will attempt to
                              determine which are optical duplicates.  Please be aware that if you raise this value too
                              high and do encounter a very large set of duplicate reads, it will severely affect the
                              runtime of this tool.  To completely disable this check, set the value to -1.  Default
                              value: 300000. 

--MAX_RECORDS_IN_RAM When writing files that need to be sorted, this will specify the number of records stored
                              in RAM before spilling to disk. Increasing this number reduces the number of file handles
                              needed to sort the file, and increases the amount of RAM needed.  Default value: 500000. 

--MAX_SEQUENCES_FOR_DISK_READ_ENDS_MAP,-MAX_SEQS 
                              This option is obsolete. ReadEnds will always be spilled to disk.  Default value: 50000. 

--MOLECULAR_IDENTIFIER_TAG 
                              SAM tag to uniquely identify the molecule from which a read was derived.  Use of this
                              option requires that the BARCODE_TAG option be set to a non null value.  Default null. 
                              Default value: null. 

--OPTICAL_DUPLICATE_PIXEL_DISTANCE 
                              The maximum offset between two duplicate clusters in order to consider them optical
                              duplicates. The default is appropriate for unpatterned versions of the Illumina platform.
                              For the patterned flowcell models, 2500 is moreappropriate. For other platforms and
                              models, users should experiment to find what works best.  Default value: 100. 

--PROGRAM_GROUP_COMMAND_LINE,-PG_COMMAND 
                              Value of CL tag of PG record to be created. If not supplied the command line will be
                              detected automatically.  Default value: null. 

--PROGRAM_GROUP_NAME,-PG_NAME 
                              Value of PN tag of PG record to be created.  Default value: MarkDuplicates. 

--PROGRAM_GROUP_VERSION,-PG_VERSION 
                              Value of VN tag of PG record to be created. If not specified, the version will be detected
                              automatically.  Default value: null. 

--PROGRAM_RECORD_ID,-PG 
                              The program record ID for the @PG record(s) created by this program. Set to null to
                              disable PG record creation.  This string may have a suffix appended to avoid collision
                              with other program record IDs.  Default value: MarkDuplicates. 

--QUIET              Whether to suppress job-summary info on System.err.  Default value: false. Possible
                              values: {true, false} 

--READ_NAME_REGEX     MarkDuplicates can use the tile and cluster positions to estimate the rate of optical
                              duplication in addition to the dominant source of duplication, PCR, to provide a more
                              accurate estimation of library size. By default (with no READ_NAME_REGEX specified),
                              MarkDuplicates will attempt to extract coordinates using a split on ':' (see Note below). 
                              Set READ_NAME_REGEX to 'null' to disable optical duplicate detection. Note that without
                              optical duplicate counts, library size estimation will be less accurate. If the read name
                              does not follow a standard Illumina colon-separation convention, but does contain tile and
                              x,y coordinates, a regular expression can be specified to extract three variables:
                              tile/region, x coordinate and y coordinate from a read name. The regular expression must
                              contain three capture groups for the three variables, in order. It must match the entire
                              read name.   e.g. if field names were separated by semi-colon (';') this example regex
                              could be specified      (?:.*;)?([0-9]+)[^;]*;([0-9]+)[^;]*;([0-9]+)[^;]*$ Note that if no
                              READ_NAME_REGEX is specified, the read name is split on ':'.   For 5 element names, the
                              3rd, 4th and 5th elements are assumed to be tile, x and y values.   For 7 element names
                              (CASAVA 1.8), the 5th, 6th, and 7th elements are assumed to be tile, x and y values. 
                              Default value: . 

--READ_ONE_BARCODE_TAG 
                              Read one barcode SAM tag (ex. BX for 10X Genomics)  Default value: null. 

--READ_TWO_BARCODE_TAG 
                              Read two barcode SAM tag (ex. BX for 10X Genomics)  Default value: null. 

--REFERENCE_SEQUENCE,-R 
                              Reference sequence file.  Default value: null. 

--REMOVE_DUPLICATES  If true do not write duplicates to the output file instead of writing them with
                              appropriate flags set.  Default value: false. Possible values: {true, false} 

--REMOVE_SEQUENCING_DUPLICATES 
                              If true remove 'optical' duplicates and other duplicates that appear to have arisen from
                              the sequencing process instead of the library preparation process, even if
                              REMOVE_DUPLICATES is false. If REMOVE_DUPLICATES is true, all duplicates are removed and
                              this option is ignored.  Default value: false. Possible values: {true, false} 

--SORTING_COLLECTION_SIZE_RATIO 
                              This number, plus the maximum RAM available to the JVM, determine the memory footprint
                              used by some of the sorting collections.  If you are running out of memory, try reducing
                              this number.  Default value: 0.25. 

--TAG_DUPLICATE_SET_MEMBERS 
                              If a read appears in a duplicate set, add two tags. The first tag, DUPLICATE_SET_SIZE_TAG
                              (DS), indicates the size of the duplicate set. The smallest possible DS value is 2 which
                              occurs when two reads map to the same portion of the reference only one of which is marked
                              as duplicate. The second tag, DUPLICATE_SET_INDEX_TAG (DI), represents a unique identifier
                              for the duplicate set to which the record belongs. This identifier is the index-in-file of
                              the representative read that was selected out of the duplicate set.  Default value: false.
                              Possible values: {true, false} 

--TAGGING_POLICY 
                              Determines how duplicate types are recorded in the DT optional attribute.  Default value:
                              DontTag. Possible values: {DontTag, OpticalOnly, All} 

--TMP_DIR               One or more directories with space available to be used by this program for temporary
                              storage of working files  This argument may be specified 0 or more times. Default value:
                              null. 

--USE_JDK_DEFLATER,-use_jdk_deflater 
                              Use the JDK Deflater instead of the Intel Deflater for writing compressed output  Default
                              value: false. Possible values: {true, false} 

--USE_JDK_INFLATER,-use_jdk_inflater 
                              Use the JDK Inflater instead of the Intel Inflater for reading compressed input  Default
                              value: false. Possible values: {true, false} 

--VALIDATION_STRINGENCY 
                              Validation stringency for all SAM files read by this program.  Setting stringency to
                              SILENT can improve performance when processing a BAM file in which variable-length data
                              (read, qualities, tags) do not otherwise need to be decoded.  Default value: STRICT.
                              Possible values: {STRICT, LENIENT, SILENT} 

--VERBOSITY         Control verbosity of logging.  Default value: INFO. Possible values: {ERROR, WARNING,
                              INFO, DEBUG} 

--version            display the version number for this tool  Default value: false. Possible values: {true,
                              false} 

Advanced Arguments:

--showHidden         display hidden arguments  Default value: false. Possible values: {true, false} 

Tool returned:
1
```
