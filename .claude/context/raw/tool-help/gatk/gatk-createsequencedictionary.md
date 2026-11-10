# gatk CreateSequenceDictionary

```
Using GATK jar /opt/pixi-project/.pixi/envs/default/share/gatk4-4.6.2.0-0/gatk-package-4.6.2.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/pixi-project/.pixi/envs/default/share/gatk4-4.6.2.0-0/gatk-package-4.6.2.0-local.jar CreateSequenceDictionary --help
USAGE: CreateSequenceDictionary [arguments]

Creates a sequence dictionary for a reference sequence.  This tool creates a sequence dictionary file (with ".dict"
extension) from a reference sequence provided in FASTA format, which is required by many processing and analysis tools.
The output file contains a header but no SAMRecords, and the header contains only sequence records.The
reference sequence can be gzipped (both .fasta and .fasta.gz are supported).
## Usage example:

```
java -jar
picard.jar CreateSequenceDictionary \       R=reference.fasta \       O=reference.dict
```

Version:4.6.2.0

Required Arguments:

--REFERENCE,-R Input reference fasta or fasta.gz  Required. 

Optional Arguments:

--ALT_NAMES,-AN         Optional file containing the alternative names for the contigs. Tools may use this
                              information to consider different contig notations as identical (e.g: 'chr1' and '1'). The
                              alternative names will be put into the appropriate @AN annotation for each contig. No
                              header. First column is the original name, the second column is an alternative name. One
                              contig may have more than one alternative name.  Default value: null. 

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--COMPRESSION_LEVEL  Compression level for all compressed files created (e.g. BAM and VCF).  Default value: 2. 

--CREATE_INDEX       Whether to create an index when writing VCF or coordinate sorted BAM output.  Default
                              value: false. Possible values: {true, false} 

--CREATE_MD5_FILE    Whether to create an MD5 digest for any BAM or FASTQ files created.    Default value:
                              false. Possible values: {true, false} 

--GENOME_ASSEMBLY,-AS Put into AS field of sequence dictionary entry if supplied  Default value: null. 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

--MAX_RECORDS_IN_RAM When writing files that need to be sorted, this will specify the number of records stored
                              in RAM before spilling to disk. Increasing this number reduces the number of file handles
                              needed to sort the file, and increases the amount of RAM needed.  Default value: 500000. 

--NUM_SEQUENCES      Stop after writing this many sequences.  For testing.  Default value: 2147483647. 

--OUTPUT,-O    Output SAM file containing only the sequence dictionary. By default it will use the base
                              name of the input reference with the .dict extension  Default value: null. 

--QUIET              Whether to suppress job-summary info on System.err.  Default value: false. Possible
                              values: {true, false} 

--SPECIES,-SP         Put into SP field of sequence dictionary entry  Default value: null. 

--TMP_DIR               One or more directories with space available to be used by this program for temporary
                              storage of working files  This argument may be specified 0 or more times. Default value:
                              null. 

--TRUNCATE_NAMES_AT_WHITESPACE 
                              Make sequence name the first word from the > line in the fasta file.  By default the
                              entire contents of the > line is used, excluding leading and trailing whitespace.  Default
                              value: true. Possible values: {true, false} 

--URI,-UR             Put into UR field of sequence dictionary entry.  If not supplied, input reference file is
                              used  Default value: null. 

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
