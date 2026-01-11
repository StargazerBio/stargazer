# gatk SortSam

```
Using GATK jar /opt/gatk/gatk-package-4.6.1.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/gatk/gatk-package-4.6.1.0-local.jar SortSam --help
USAGE: SortSam [arguments]

This tool sorts the input SAM or BAM file by coordinate, queryname (QNAME), or some other property of the SAM record.
The SortOrder of a SAM/BAM/CRAM file is found in the SAM file header tag @HD in the field labeled SO.  
 For a
coordinate sorted SAM/BAM/CRAM file, read alignments are sorted first by the reference sequence name (RNAME) field using
the reference sequence dictionary (@SQ tag).  Alignments within these subgroups are secondarily sorted using the
left-most mapping position of the read (POS).  Subsequent to this sorting scheme, alignments are listed
arbitrarily.
 For queryname-sorted alignments, the tool orders records deterministically by queryname field
followed by record strand orientation flag, primary record flag, and secondary alignment flag. This ordering may change
in future versions. 
## Usage example:

```
java -jar picard.jar SortSam \      I=input.bam
\      O=sorted.bam \      SORT_ORDER=coordinate
```

Version:4.6.1.0

Required Arguments:

--INPUT,-I              The SAM, BAM or CRAM file to sort.  Required. 

--OUTPUT,-O             The sorted SAM, BAM or CRAM output file.   Required. 

--SORT_ORDER,-SO   Sort order of output file.   Required. queryname (Sorts according to the readname. This
                              will place read-pairs and other derived reads (secondary and supplementary) adjacent to
                              each other. Note that the readnames are compared lexicographically, even though they may
                              include numbers. In paired reads, Read1 sorts before Read2.)
                              coordinate (Sorts primarily according to the SEQ and POS fields of the record. The
                              sequence will sorted according to the order in the sequence dictionary, taken from from
                              the header of the file. Within each reference sequence, the reads are sorted by the
                              position. Unmapped reads whose mates are mapped will be placed near their mates. Unmapped
                              read-pairs are placed after all the mapped reads and their mates.)
                              duplicate (Sorts the reads so that duplicates reads are adjacent. Required that the
                              mate-cigar (MC) tag is present. The resulting will be sorted by library, unclipped 5-prime
                              position, orientation, and mate's unclipped 5-prime position.)

Optional Arguments:

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--COMPRESSION_LEVEL  Compression level for all compressed files created (e.g. BAM and VCF).  Default value: 2. 

--CREATE_INDEX       Whether to create an index when writing VCF or coordinate sorted BAM output.  Default
                              value: false. Possible values: {true, false} 

--CREATE_MD5_FILE    Whether to create an MD5 digest for any BAM or FASTQ files created.    Default value:
                              false. Possible values: {true, false} 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

--MAX_RECORDS_IN_RAM When writing files that need to be sorted, this will specify the number of records stored
                              in RAM before spilling to disk. Increasing this number reduces the number of file handles
                              needed to sort the file, and increases the amount of RAM needed.  Default value: 500000. 

--QUIET              Whether to suppress job-summary info on System.err.  Default value: false. Possible
                              values: {true, false} 

--REFERENCE_SEQUENCE,-R 
                              Reference sequence file.  Default value: null. 

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
