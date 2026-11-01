# samtools faidx

Indexes or queries regions from a FASTA file.

## Synopsis
```bash
samtools faidx ref.fasta [region1 [...]]
```

## Description

Index reference sequence in the FASTA format or extract subsequence from indexed reference sequence.

- If no region is specified, `faidx` will index the file and create `<ref.fasta>.fai` on the disk
- If regions are specified, the subsequences will be retrieved and printed to stdout in the FASTA format

The input and output can be files compressed in the BGZF format. When output is compressed, the default compression level is 4.

The sequences in the input file should all have different names. If they do not, indexing will emit a warning about duplicate sequences and retrieval will only produce subsequences from the first sequence with the duplicated name.

FASTQ files can be read and indexed by this command. Without using `--fastq` any extracted subsequence will be in FASTA format.

## Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Write FASTA to file rather than to stdout. If FILE ends with `.gz`, `.bgz` or `.bgzf` then it will be BGZF compressed. |
| `-n, --length INT` | Length for FASTA sequence line wrapping. If zero, do not line wrap. Defaults to the line length in the input file. |
| `-c, --continue` | Continue working if a non-existent region is requested. |
| `-r, --region-file FILE` | Read regions from a file. Format is `chr:from-to`, one per line. |
| `-f, --fastq` | Read FASTQ files and output extracted sequences in FASTQ format. Same as using `samtools fqidx`. |
| `-i, --reverse-complement` | Output the sequence as the reverse complement. When this option is used, `/rc` will be appended to the sequence names. To turn this off or change the string appended, use the `--mark-strand` option. |
| `--fai-idx FILE` | Read/Write to specified index file. |
| `--gzi-idx FILE` | Read/Write to specified compressed file index (used with `.gz` files). |
| `-h, --help` | Print help message and exit. |
| `--output-fmt-option OPT=VAL` | Set the output format options, `level=0..9` for compression level 0 to 9. |
| `--write-index` | Create index for the output sequence data along with the output, in same path as `<output name>.fai`, `<outputname>.gzi`. This option is valid only for file output. |
| `-@, --threads N` | Set the number of extra threads for operations on compressed files. |

### --mark-strand TYPE

Append strand indicator to sequence name. TYPE can be one of:

| Type | Description |
|------|-------------|
| `rc` | Append `/rc` when writing the reverse complement. This is the default. |
| `no` | Do not append anything. |
| `sign` | Append `(+)` for forward strand or `(-)` for reverse complement. This matches the output of `bedtools getfasta -s`. |
| `custom,<pos>,<neg>` | Append string `<pos>` to names when writing the forward strand and `<neg>` when writing the reverse strand. Spaces are preserved, so it is possible to move the indicator into the comment part of the description line by including a leading space in the strings `<pos>` and `<neg>`. |