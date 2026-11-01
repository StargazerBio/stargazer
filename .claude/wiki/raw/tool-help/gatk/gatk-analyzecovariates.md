# gatk AnalyzeCovariates

```
Using GATK jar /opt/gatk/gatk-package-4.6.1.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/gatk/gatk-package-4.6.1.0-local.jar AnalyzeCovariates --help
USAGE: AnalyzeCovariates [arguments]

Evaluate and compare base quality score recalibration (BQSR) tables
Version:4.6.1.0

Optional Arguments:

--after-report-file,-after 
                              file containing the BQSR second-pass report file  Default value: null. 

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--before-report-file,-before 
                              file containing the BQSR first-pass report file  Default value: null. 

--bqsr-recal-file,-bqsr Input covariates table file for on-the-fly base quality score recalibration  Default
                              value: null. 

--gatk-config-file    A configuration file to use with the GATK.  Default value: null. 

--gcs-max-retries,-gcs-retries 
                              If the GCS bucket channel errors out, how many times it will attempt to re-initiate the
                              connection  Default value: 20. 

--gcs-project-for-requester-pays 
                              Project to bill when accessing "requester pays" buckets. If unset, these buckets cannot be
                              accessed.  User must have storage.buckets.get permission on the bucket being accessed. 
                              Default value: . 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

--ignore-last-modification-times 
                              do not emit warning messages related to suspicious last modification time order of inputs 
                              Default value: false. Possible values: {true, false} 

--intermediate-csv-file,-csv 
                              location of the csv intermediate file  Default value: null. 

--plots-report-file,-plots 
                              location of the output report  Default value: null. 

--QUIET              Whether to suppress job-summary info on System.err.  Default value: false. Possible
                              values: {true, false} 

--tmp-dir           Temp directory to use.  Default value: null. 

--use-jdk-deflater,-jdk-deflater 
                              Whether to use the JdkDeflater (as opposed to IntelDeflater)  Default value: false.
                              Possible values: {true, false} 

--use-jdk-inflater,-jdk-inflater 
                              Whether to use the JdkInflater (as opposed to IntelInflater)  Default value: false.
                              Possible values: {true, false} 

--verbosity         Control verbosity of logging.  Default value: INFO. Possible values: {ERROR, WARNING,
                              INFO, DEBUG} 

--version            display the version number for this tool  Default value: false. Possible values: {true,
                              false} 

Advanced Arguments:

--showHidden         display hidden arguments  Default value: false. Possible values: {true, false} 

Tool returned:
0
```
