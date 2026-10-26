# gatk MergeBamAlignment

```
Using GATK jar /opt/gatk/gatk-package-4.6.1.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/gatk/gatk-package-4.6.1.0-local.jar MergeBamAlignment --help
USAGE: MergeBamAlignment [arguments]

Merge alignment data from a SAM or BAM with data in an unmapped BAM file.  
## Summary

A command-line tool for merging BAM/SAM alignment info from a third-party aligner with the data in an unmapped BAM file,
producing a third BAM file that has alignment data (from the aligner) and all the remaining data from the unmapped BAM.

Quick note: this is **not** a tool for taking multiple sam files and creating a bigger file by merging them. For that
use-case, see {@link MergeSamFiles}.

## Details

Many alignment tools (still!) require fastq format input. The unmapped bam may contain useful information that will be
lost in the conversion to fastq (meta-data like sample alias, library, barcodes, etc., and read-level tags.)

This tool takes an unaligned bam with meta-data, and the aligned bam produced by calling {@link SamToFastq} and then
passing the result to an aligner/mapper. It produces a new SAM file that includes all aligned and unaligned reads and
also carries forward additional read attributes from the unmapped BAM (attributes that are otherwise lost in the process
of converting to fastq). The resulting file will be valid for use by Picard and GATK tools.

The output may be coordinate-sorted, in which case the tags, NM, MD, and UQ will be calculated and populated, or
query-name sorted, in which case the tags will not be calculated or populated.

## Usage example:

java -jar picard.jar MergeBamAlignment \
ALIGNED=aligned.bam \
UNMAPPED=unmapped.bam \
O=merge_alignments.bam \
R=reference_sequence.fasta

## Note about required arguments

The aligned reads must be specified using either the ALIGNED_BAM or READ1_ALIGNED_BAM and READ2_ALIGNED_BAM arguments. 
Without aligned reads specified in one of those manners, the tool will not run.
## Caveats

This tool has been developing for a while and many arguments have been added to it over the years. You may be
particularly interested in the following (partial) list:

* CLIP_ADAPTERS -- Whether to (soft-)clip the ends of the reads that are identified as belonging to adapters
* IS_BISULFITE_SEQUENCE -- Whether the sequencing originated from bisulfite sequencing, in which case NM will be
calculated differently
* ALIGNER_PROPER_PAIR_FLAGS -- Use if the aligner that was used cannot be trusted to set the "Proper pair" flag and
then the tool will set this flag based on orientation and distance between pairs.
* ADD_MATE_CIGAR -- Whether to use this opportunity to add the MC tag to each read.
* UNMAP_CONTAMINANT_READS (and MIN_UNCLIPPED_BASES) -- Whether to identify extremely short alignments (with clipping
on both sides) as cross-species contamination and unmap the reads.

Version:4.6.1.0

Required Arguments:

--OUTPUT,-O             Merged SAM or BAM file to write to.  Required. 

--REFERENCE_SEQUENCE,-R 
                              Reference sequence file.  Required. 

--UNMAPPED_BAM,-UNMAPPED 
                              Original SAM or BAM file of unmapped reads, which must be in queryname order.  Reads MUST
                              be unmapped.  Required. 

Optional Arguments:

--ADD_MATE_CIGAR,-MC Adds the mate CIGAR tag (MC) if true, does not if false.  Default value: true. Possible
                              values: {true, false} 

--ADD_PG_TAG_TO_READS 
                              Add PG tag to each read in a SAM or BAM  Default value: true. Possible values: {true,
                              false} 

--ALIGNED_BAM,-ALIGNED  SAM or BAM file(s) with alignment data.  This argument may be specified 0 or more times.
                              Default value: null.  Cannot be used in conjunction with argument(s) READ1_ALIGNED_BAM
                              (R1_ALIGNED) READ2_ALIGNED_BAM (R2_ALIGNED)

--ALIGNED_READS_ONLY Whether to output only aligned reads.    Default value: false. Possible values: {true,
                              false} 

--ALIGNER_PROPER_PAIR_FLAGS 
                              Use the aligner's idea of what a proper pair is rather than computing in this program. 
                              Default value: false. Possible values: {true, false} 

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--ATTRIBUTES_TO_REMOVE 
                              Attributes from the alignment record that should be removed when merging.  This overrides
                              ATTRIBUTES_TO_RETAIN if they share common tags.  This argument may be specified 0 or more
                              times. Default value: null. 

--ATTRIBUTES_TO_RETAIN 
                              Reserved alignment attributes (tags starting with X, Y, or Z) that should be brought over
                              from the alignment data when merging.  This argument may be specified 0 or more times.
                              Default value: null. 

--ATTRIBUTES_TO_REVERSE,-RV 
                              Attributes on negative strand reads that need to be reversed.  This argument may be
                              specified 0 or more times. Default value: [OQ, U2]. 

--ATTRIBUTES_TO_REVERSE_COMPLEMENT,-RC 
                              Attributes on negative strand reads that need to be reverse complemented.  This argument
                              may be specified 0 or more times. Default value: [E2, SQ]. 

--CLIP_ADAPTERS      Whether to clip adapters where identified.  Default value: true. Possible values: {true,
                              false} 

--CLIP_OVERLAPPING_READS 
                              For paired reads, clip the 3' end of each read if necessary so that it does not extend
                              past the 5' end of its mate.  Reads are first soft clipped so that the 3' aligned end of
                              each read does not extend past the 5' aligned end of its mate.  If
                              HARD_CLIP_OVERLAPPING_READS is also true, then reads are additionally hard clipped so that
                              the 3' unclipped end of each read does not extend past the 5' unclipped end of its mate. 
                              Hard clipped bases and their qualities are stored in the XB and XQ tags, respectively. 
                              Default value: true. Possible values: {true, false} 

--COMPRESSION_LEVEL  Compression level for all compressed files created (e.g. BAM and VCF).  Default value: 2. 

--CREATE_INDEX       Whether to create an index when writing VCF or coordinate sorted BAM output.  Default
                              value: false. Possible values: {true, false} 

--CREATE_MD5_FILE    Whether to create an MD5 digest for any BAM or FASTQ files created.    Default value:
                              false. Possible values: {true, false} 

--EXPECTED_ORIENTATIONS,-ORIENTATIONS 
                              The expected orientation of proper read pairs. Replaces JUMP_SIZE  This argument may be
                              specified 0 or more times. Default value: null. Possible values: {FR, RF, TANDEM}  Cannot
                              be used in conjunction with argument(s) JUMP_SIZE (JUMP)

--HARD_CLIP_OVERLAPPING_READS 
                              If true, hard clipping will be applied to overlapping reads.  By default, soft clipping is
                              used.  Default value: false. Possible values: {true, false} 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

--INCLUDE_SECONDARY_ALIGNMENTS 
                              If false, do not write secondary alignments to output.  Default value: true. Possible
                              values: {true, false} 

--IS_BISULFITE_SEQUENCE 
                              Whether the lane is bisulfite sequence (used when calculating the NM tag).  Default value:
                              false. Possible values: {true, false} 

--JUMP_SIZE,-JUMP    The expected jump size (required if this is a jumping library). Deprecated. Use
                              EXPECTED_ORIENTATIONS instead  Default value: null.  Cannot be used in conjunction with
                              argument(s) EXPECTED_ORIENTATIONS (ORIENTATIONS)

--MATCHING_DICTIONARY_TAGS 
                              List of Sequence Records tags that must be equal (if present) in the reference dictionary
                              and in the aligned file. Mismatching tags will cause an error if in this list, and a
                              warning otherwise.  This argument may be specified 0 or more times. Default value: [M5,
                              LN]. 

--MAX_INSERTIONS_OR_DELETIONS,-MAX_GAPS 
                              The maximum number of insertions or deletions permitted for an alignment to be included.
                              Alignments with more than this many insertions or deletions will be ignored. Set to -1 to
                              allow any number of insertions or deletions.  Default value: 1. 

--MAX_RECORDS_IN_RAM When writing files that need to be sorted, this will specify the number of records stored
                              in RAM before spilling to disk. Increasing this number reduces the number of file handles
                              needed to sort the file, and increases the amount of RAM needed.  Default value: 500000. 

--MIN_UNCLIPPED_BASES 
                              If UNMAP_CONTAMINANT_READS is set, require this many unclipped bases or else the read will
                              be marked as contaminant.  Default value: 32. 

--PAIRED_RUN,-PE     DEPRECATED. This argument is ignored and will be removed.  Default value: true. Possible
                              values: {true, false} 

--PRIMARY_ALIGNMENT_STRATEGY 
                              Strategy for selecting primary alignment when the aligner has provided more than one
                              alignment for a pair or fragment, and none are marked as primary, more than one is marked
                              as primary, or the primary alignment is filtered out for some reason. For all strategies,
                              ties are resolved arbitrarily.  Default value: BestMapq. BestMapq (Expects that multiple
                              alignments will be correlated with HI tag, and prefers the pair of alignments with the
                              largest MAPQ, in the absence of a primary selected by the aligner.)
                              EarliestFragment (Prefers the alignment which maps the earliest base in the read. Note
                              that EarliestFragment may not be used for paired reads.)
                              BestEndMapq (Appropriate for cases in which the aligner is not pair-aware, and does not
                              output the HI tag. It simply picks the alignment for each end with the highest MAPQ, and
                              makes those alignments primary, regardless of whether the two alignments make sense
                              together.)
                              MostDistant (Appropriate for a non-pair-aware aligner. Picks the alignment pair with the
                              largest insert size. If all alignments would be chimeric, it picks the alignments for each
                              end with the best MAPQ. )

--PROGRAM_GROUP_COMMAND_LINE,-PG_COMMAND 
                              The command line of the program group (if not supplied by the aligned file).  Default
                              value: null. 

--PROGRAM_GROUP_NAME,-PG_NAME 
                              The name of the program group (if not supplied by the aligned file).  Default value: null.

--PROGRAM_GROUP_VERSION,-PG_VERSION 
                              The version of the program group (if not supplied by the aligned file).  Default value:
                              null. 

--PROGRAM_RECORD_ID,-PG 
                              The program group ID of the aligner (if not supplied by the aligned file).  Default value:
                              null. 

--QUIET              Whether to suppress job-summary info on System.err.  Default value: false. Possible
                              values: {true, false} 

--READ1_ALIGNED_BAM,-R1_ALIGNED 
                              SAM or BAM file(s) with alignment data from the first read of a pair.  This argument may
                              be specified 0 or more times. Default value: null.  Cannot be used in conjunction with
                              argument(s) ALIGNED_BAM (ALIGNED)

--READ1_TRIM,-R1_TRIM 
                              The number of bases trimmed from the beginning of read 1 prior to alignment  Default
                              value: 0. 

--READ2_ALIGNED_BAM,-R2_ALIGNED 
                              SAM or BAM file(s) with alignment data from the second read of a pair.  This argument may
                              be specified 0 or more times. Default value: null.  Cannot be used in conjunction with
                              argument(s) ALIGNED_BAM (ALIGNED)

--READ2_TRIM,-R2_TRIM 
                              The number of bases trimmed from the beginning of read 2 prior to alignment  Default
                              value: 0. 

--SORT_ORDER,-SO   The order in which the merged reads should be output.  Default value: coordinate. Possible
                              values: {unsorted, queryname, coordinate, duplicate, unknown} 

--TMP_DIR               One or more directories with space available to be used by this program for temporary
                              storage of working files  This argument may be specified 0 or more times. Default value:
                              null. 

--UNMAP_CONTAMINANT_READS,-UNMAP_CONTAM 
                              Detect reads originating from foreign organisms (e.g. bacterial DNA in a non-bacterial
                              sample),and unmap + label those reads accordingly.  Default value: false. Possible values:
                              {true, false} 

--UNMAPPED_READ_STRATEGY 
                              How to deal with alignment information in reads that are being unmapped (e.g. due to
                              cross-species contamination.) Currently ignored unless UNMAP_CONTAMINANT_READS = true.
                              Note that the DO_NOT_CHANGE strategy will actually reset the cigar and set the mapping
                              quality on unmapped reads since otherwisethe result will be an invalid record. To force no
                              change use the DO_NOT_CHANGE_INVALID strategy.  Default value: DO_NOT_CHANGE. Possible
                              values: {COPY_TO_TAG, DO_NOT_CHANGE, DO_NOT_CHANGE_INVALID, MOVE_TO_TAG} 

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
