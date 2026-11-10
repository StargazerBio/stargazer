# gatk IndexFeatureFile

```
Using GATK jar /opt/pixi-project/.pixi/envs/default/share/gatk4-4.6.2.0-0/gatk-package-4.6.2.0-local.jar
Running:
    java -Dsamjdk.use_async_io_read_samtools=false -Dsamjdk.use_async_io_write_samtools=true -Dsamjdk.use_async_io_write_tribble=false -Dsamjdk.compression_level=2 -jar /opt/pixi-project/.pixi/envs/default/share/gatk4-4.6.2.0-0/gatk-package-4.6.2.0-local.jar IndexFeatureFile --help
USAGE: IndexFeatureFile [arguments]

Creates an index for a feature file, e.g. VCF or BED file.
Version:4.6.2.0

Required Arguments:

--input,-I          Feature file (eg., VCF or BED file) to index. Must be in a tribble-supported format 
                              Required. 

Optional Arguments:

--arguments_file        read one or more arguments files and add them to the command line  This argument may be
                              specified 0 or more times. Default value: null. 

--gatk-config-file    A configuration file to use with the GATK.  Default value: null. 

--gcs-max-retries,-gcs-retries 
                              If the GCS bucket channel errors out, how many times it will attempt to re-initiate the
                              connection  Default value: 20. 

--gcs-project-for-requester-pays 
                              Project to bill when accessing "requester pays" buckets. If unset, these buckets cannot be
                              accessed.  User must have storage.buckets.get permission on the bucket being accessed. 
                              Default value: . 

--help,-h            display the help message  Default value: false. Possible values: {true, false} 

--output,-O         The output index file. If missing, the tool will create an index file in the same
                              directory as the input file.  Default value: null. 

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
