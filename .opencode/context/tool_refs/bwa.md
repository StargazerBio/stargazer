# bwa - Burrows-Wheeler Alignment Tool

## Synopsis
```bash
bwa index ref.fa

bwa mem ref.fa reads.fq > aln-se.sam

bwa mem ref.fa read1.fq read2.fq > aln-pe.sam

bwa aln ref.fa short_read.fq > aln_sa.sai

bwa samse ref.fa aln_sa.sai short_read.fq > aln-se.sam

bwa sampe ref.fa aln_sa1.sai aln_sa2.sai read1.fq read2.fq > aln-pe.sam

bwa bwasw ref.fa long_read.fq > aln.sam
```

## Description

BWA is a software package for mapping low-divergent sequences against a large reference genome, such as the human genome. It consists of three algorithms:

| Algorithm | Read Length | Description |
|-----------|-------------|-------------|
| BWA-backtrack | Up to 100bp | Designed for Illumina sequence reads |
| BWA-SW | 70bp to 1Mbp | Long-read support with split alignment |
| BWA-MEM | 70bp to 1Mbp | Latest algorithm, generally recommended for high-quality queries |

BWA-MEM is generally recommended as it is faster and more accurate. It also has better performance than BWA-backtrack for 70-100bp Illumina reads.

For all algorithms, BWA first needs to construct the FM-index for the reference genome (the `index` command). Alignment algorithms are invoked with different sub-commands:

- `aln/samse/sampe` for BWA-backtrack
- `bwasw` for BWA-SW
- `mem` for BWA-MEM

---

## Commands and Options

### index
```bash
bwa index [-p prefix] [-a algoType] <in.db.fasta>
```

Index database sequences in the FASTA format.

| Option | Description |
|--------|-------------|
| `-p STR` | Prefix of the output database [same as db filename] |
| `-a STR` | Algorithm for constructing BWT index (see below) |

**Algorithm options for `-a`:**

| Algorithm | Description |
|-----------|-------------|
| `is` | IS linear-time algorithm for constructing suffix array. Requires 5.37N memory where N is the size of the database. Moderately fast, but does not work with database larger than 2GB. This is the default. |
| `bwtsw` | Algorithm implemented in BWT-SW. Works with the whole human genome. |

---

### mem
```bash
bwa mem [-aCHMpP] [-t nThreads] [-k minSeedLen] [-w bandWidth] [-d zDropoff] [-r seedSplitRatio] [-c maxOcc] [-A matchScore] [-B mmPenalty] [-O gapOpenPen] [-E gapExtPen] [-L clipPen] [-U unpairPen] [-R RGline] [-v verboseLevel] db.prefix reads.fq [mates.fq]
```

Align 70bp-1Mbp query sequences with the BWA-MEM algorithm. The algorithm works by seeding alignments with maximal exact matches (MEMs) and then extending seeds with the affine-gap Smith-Waterman algorithm (SW).

**Input modes:**

- If `mates.fq` is absent and `-p` is not set: single-end reads
- If `mates.fq` is present: paired-end (i-th read in each file constitute a pair)
- If `-p` is used: interleaved paired-end (2i-th and (2i+1)-th reads are pairs)

The BWA-MEM algorithm performs local alignment and may produce multiple primary alignments for different parts of a query sequence. This is crucial for long sequences. Some tools (e.g., Picard's markDuplicates) do not work with split alignments; use `-M` to flag shorter split hits as secondary.

| Option | Description | Default |
|--------|-------------|---------|
| `-t INT` | Number of threads | 1 |
| `-k INT` | Minimum seed length. Matches shorter than INT will be missed. | 19 |
| `-w INT` | Band width. Gaps longer than INT will not be found. | 100 |
| `-d INT` | Off-diagonal X-dropoff (Z-dropoff). Stop extension when the difference between best and current extension score is above \|i-j\|*A+INT. | 100 |
| `-r FLOAT` | Trigger re-seeding for a MEM longer than minSeedLen*FLOAT. Larger value yields fewer seeds (faster but lower accuracy). | 1.5 |
| `-c INT` | Discard a MEM if it has more than INT occurrences in the genome. | 10000 |
| `-P` | In paired-end mode, perform SW to rescue missing hits only but do not try to find hits that fit a proper pair. | - |
| `-A INT` | Matching score | 1 |
| `-B INT` | Mismatch penalty. Sequence error rate ≈ {0.75 * exp[-log(4) * B/A]}. | 4 |
| `-O INT` | Gap open penalty | 6 |
| `-E INT` | Gap extension penalty. A gap of length k costs O + k*E. | 1 |
| `-L INT` | Clipping penalty. Clipping not applied if best score reaching end of query > best SW score minus this penalty. | 5 |
| `-U INT` | Penalty for an unpaired read pair. | 9 |
| `-p` | Assume first input query file is interleaved paired-end FASTA/Q. | - |
| `-R STR` | Complete read group header line. `\t` will be converted to TAB. Example: `@RG\tID:foo\tSM:bar` | null |
| `-T INT` | Don't output alignment with score lower than INT. | 30 |
| `-a` | Output all found alignments for single-end or unpaired paired-end reads (flagged as secondary). | - |
| `-C` | Append FASTA/Q comment to SAM output. Comment must conform to SAM spec (e.g., `BC:Z:CGTAC`). | - |
| `-H` | Use hard clipping 'H' in the SAM output. Reduces redundancy when mapping long contigs or BAC sequences. | - |
| `-M` | Mark shorter split hits as secondary (for Picard compatibility). | - |
| `-v INT` | Verbose level: 0=disabled, 1=errors, 2=warnings+errors, 3=all messages, 4+=debugging. | 3 |

---

### aln
```bash
bwa aln [-n maxDiff] [-o maxGapO] [-e maxGapE] [-d nDelTail] [-i nIndelEnd] [-k maxSeedDiff] [-l seedLen] [-t nThrds] [-cRN] [-M misMsc] [-O gapOsc] [-E gapEsc] [-q trimQual] <in.db.fasta> <in.query.fq> > <out.sai>
```

Find the SA coordinates of the input reads. Maximum `maxSeedDiff` differences are allowed in the first `seedLen` subsequence and maximum `maxDiff` differences are allowed in the whole sequence.

| Option | Description | Default |
|--------|-------------|---------|
| `-n NUM` | Maximum edit distance if INT, or fraction of missing alignments given 2% uniform base error rate if FLOAT. | 0.04 |
| `-o INT` | Maximum number of gap opens | 1 |
| `-e INT` | Maximum number of gap extensions. -1 for k-difference mode (disallowing long gaps). | -1 |
| `-d INT` | Disallow a long deletion within INT bp towards the 3'-end | 16 |
| `-i INT` | Disallow an indel within INT bp towards the ends | 5 |
| `-l INT` | Take the first INT subsequence as seed. If INT > query length, seeding is disabled. Typically 25-35 for `-k 2`. | inf |
| `-k INT` | Maximum edit distance in the seed | 2 |
| `-t INT` | Number of threads | 1 |
| `-M INT` | Mismatch penalty. BWA will not search for suboptimal hits with score lower than (bestScore-misMsc). | 3 |
| `-O INT` | Gap open penalty | 11 |
| `-E INT` | Gap extension penalty | 4 |
| `-R INT` | Proceed with suboptimal alignments if there are no more than INT equally best hits. Only affects paired-end mapping. | - |
| `-c` | Reverse query but not complement it (for color space alignment). Disabled since 0.6.x. | - |
| `-N` | Disable iterative search. All hits with ≤maxDiff differences will be found. Much slower. | - |
| `-q INT` | Parameter for read trimming. | 0 |
| `-I` | Input is in Illumina 1.3+ read format (quality = ASCII-64). | - |
| `-B INT` | Length of barcode starting from 5'-end. Barcode is trimmed before mapping and written at BC SAM tag. | 0 |
| `-b` | Input read sequence file is BAM format. | - |
| `-0` | When `-b` is specified, only use single-end reads. | - |
| `-1` | When `-b` is specified, only use the first read in a pair. | - |
| `-2` | When `-b` is specified, only use the second read in a pair. | - |

**Example for BAM input:**
```bash
bwa aln ref.fa -b1 reads.bam > 1.sai
bwa aln ref.fa -b2 reads.bam > 2.sai
bwa sampe ref.fa 1.sai 2.sai reads.bam reads.bam > aln.sam
```

---

### samse
```bash
bwa samse [-n maxOcc] <in.db.fasta> <in.sai> <in.fq> > <out.sam>
```

Generate alignments in SAM format given single-end reads. Repetitive hits will be randomly chosen.

| Option | Description | Default |
|--------|-------------|---------|
| `-n INT` | Maximum number of alignments to output in the XA tag for reads paired properly. If a read has more than INT hits, XA tag will not be written. | 3 |
| `-r STR` | Specify the read group in a format like `@RG\tID:foo\tSM:bar`. | null |

---

### sampe
```bash
bwa sampe [-a maxInsSize] [-o maxOcc] [-n maxHitPaired] [-N maxHitDis] [-P] <in.db.fasta> <in1.sai> <in2.sai> <in1.fq> <in2.fq> > <out.sam>
```

Generate alignments in SAM format given paired-end reads. Repetitive read pairs will be placed randomly.

| Option | Description | Default |
|--------|-------------|---------|
| `-a INT` | Maximum insert size for a read pair to be considered mapped properly. Only used when there are not enough good alignments to infer insert size distribution. | 500 |
| `-o INT` | Maximum occurrences of a read for pairing. Reads with more occurrences are treated as single-end. | 100000 |
| `-P` | Load the entire FM-index into memory to reduce disk operations (base-space reads only). Requires at least 1.25N bytes of memory. | - |
| `-n INT` | Maximum alignments to output in XA tag for properly paired reads. | 3 |
| `-N INT` | Maximum alignments to output in XA tag for discordant read pairs (excluding singletons). | 10 |
| `-r STR` | Specify the read group. | null |

---

### bwasw
```bash
bwa bwasw [-a matchScore] [-b mmPen] [-q gapOpenPen] [-r gapExtPen] [-t nThreads] [-w bandWidth] [-T thres] [-s hspIntv] [-z zBest] [-N nHspRev] [-c thresCoef] <in.db.fasta> <in.fq> [mate.fq]
```

Align query sequences in the `in.fq` file. When `mate.fq` is present, perform paired-end alignment. The paired-end mode only works for Illumina short-insert libraries. In paired-end mode, BWA-SW may still output split alignments but they are all marked as not properly paired.

| Option | Description | Default |
|--------|-------------|---------|
| `-a INT` | Score of a match | 1 |
| `-b INT` | Mismatch penalty | 3 |
| `-q INT` | Gap open penalty | 5 |
| `-r INT` | Gap extension penalty. A contiguous gap of size k costs q+k*r. | 2 |
| `-t INT` | Number of threads | 1 |
| `-w INT` | Band width in the banded alignment | 33 |
| `-T INT` | Minimum score threshold divided by a | 37 |
| `-c FLOAT` | Coefficient for threshold adjustment according to query length. For an l-long query, threshold = a*max{T, c*log(l)}. | 5.5 |
| `-z INT` | Z-best heuristics. Higher value increases accuracy at cost of speed. | 1 |
| `-s INT` | Maximum SA interval size for initiating a seed. Higher value increases accuracy at cost of speed. | 3 |
| `-N INT` | Minimum number of seeds supporting the resultant alignment to skip reverse alignment. | 5 |

---

## SAM Alignment Format

The output of the `aln` command is binary and designed for BWA use only. BWA outputs final alignment in SAM (Sequence Alignment/Map) format.

### SAM Columns

| Col | Field | Description |
|-----|-------|-------------|
| 1 | QNAME | Query (pair) NAME |
| 2 | FLAG | Bitwise FLAG |
| 3 | RNAME | Reference sequence NAME |
| 4 | POS | 1-based leftmost position/coordinate of clipped sequence |
| 5 | MAPQ | Mapping Quality (Phred-scaled) |
| 6 | CIGAR | Extended CIGAR string |
| 7 | MRNM | Mate Reference sequence Name ('=' if same as RNAME) |
| 8 | MPOS | 1-based Mate Position |
| 9 | ISIZE | Inferred insert SIZE |
| 10 | SEQ | Query sequence on the same strand as the reference |
| 11 | QUAL | Query quality (ASCII-33 gives the Phred base quality) |
| 12 | OPT | Variable optional fields in the format TAG:VTYPE:VALUE |

### FLAG Field Bits

| Chr | Flag | Description |
|-----|------|-------------|
| p | 0x0001 | The read is paired in sequencing |
| P | 0x0002 | The read is mapped in a proper pair |
| u | 0x0004 | The query sequence itself is unmapped |
| U | 0x0008 | The mate is unmapped |
| r | 0x0010 | Strand of the query (1 for reverse) |
| R | 0x0020 | Strand of the mate |
| 1 | 0x0040 | The read is the first read in a pair |
| 2 | 0x0080 | The read is the second read in a pair |
| s | 0x0100 | The alignment is not primary |
| f | 0x0200 | QC failure |
| d | 0x0400 | Optical or PCR duplicate |

### BWA Optional Tags

Tags starting with 'X' are specific to BWA.

| Tag | Meaning |
|-----|---------|
| NM | Edit distance |
| MD | Mismatching positions/bases |
| AS | Alignment score |
| BC | Barcode sequence |
| X0 | Number of best hits |
| X1 | Number of suboptimal hits found by BWA |
| XN | Number of ambiguous bases in the reference |
| XM | Number of mismatches in the alignment |
| XO | Number of gap opens |
| XG | Number of gap extensions |
| XT | Type: Unique/Repeat/N/Mate-sw |
| XA | Alternative hits; format: (chr,pos,CIGAR,NM;)* |
| XS | Suboptimal alignment score |
| XF | Support from forward/reverse alignment |
| XE | Number of supporting seeds |

> **Note:** XO and XG are generated by BWT search while the CIGAR string is generated by Smith-Waterman alignment. These two tags may be inconsistent with the CIGAR string. This is not a bug.

For format specification and post-processing tools, see: http://samtools.sourceforge.net