# Stargazer MVP Roadmap: Whole Genome Germline Small Variants Pipeline

This roadmap implements the NVIDIA Clara Parabricks whole genome germline small variants workflow as a Flyte v2 workflow.

**Tutorial Reference:** https://docs.nvidia.com/clara/parabricks/latest/tutorials/how-tos/wholegenomegermlinesmallvariants.html

## Current Status

### ✅ Completed Components

1. **Reference Type** (`src/stargazer/types/reference.py`)
   - Metadata-driven IPFS storage using Pinata
   - Supports multi-dimensional queries
   - Methods: `pinata_hydrate()`, `fetch()`, `get_ref_path()`, `get_file_path()`, `add_files()`

2. **samtools_faidx Task** (`src/stargazer/tasks/samtools.py`)
   - Creates `.fai` FASTA index
   - Input: Reference
   - Output: Reference with `.fai` file added
   - Test: `tests/test_samtools.py`

3. **bwa_index Task** (`src/stargazer/tasks/bwa.py`)
   - Creates BWA index files (`.amb`, `.ann`, `.bwt`, `.pac`, `.sa`)
   - Input: Reference
   - Output: Reference with BWA index files added
   - Test: `tests/test_bwa.py`

4. **Initial Workflow** (`src/stargazer/workflows/parabricks.py`)
   - Chains: Reference hydration → samtools_faidx → bwa_index
   - Demonstrates workflow composition pattern

5. **Test Infrastructure**
   - TP53 fixtures: `tests/fixtures/GRCh38_TP53.fa` (reference)
   - TP53 FASTQ: `tests/fixtures/NA12829_TP53_R1.fq.gz`, `NA12829_TP53_R2.fq.gz`
   - Pytest configuration with Flyte initialization

## Architecture Principles

1. **One Task Per Tool**: Each Parabricks/bioinformatics tool gets its own task
2. **Sensibly Defined Types**: Types (Reference, Reads, Alignment, Variants) serve as task I/O
3. **Test-First Development**: Tests and fixtures MUST exist before implementation
4. **TP53-Based Testing**: All tests use TP53 region fixtures for speed (5x faster)
5. **Metadata-Driven Storage**: All files stored in IPFS with queryable keyvalues

## Pipeline Overview

```
[FASTQ Reads] + [Reference Genome]
    ↓
[fq2bam: Alignment + Sorting + MarkDuplicates]
    ↓
[BAM]
    ↓              ↓
[DeepVariant]  [HaplotypeCaller]
    ↓              ↓
[VCF Variants] [VCF Variants]
```

---

## PHASE 1: Core Data Types

These types enable the rest of the pipeline. They follow the Reference type pattern:
- IPFS storage via Pinata
- Metadata-driven queries
- Fetch/hydrate capabilities
- Files stored as IpFile objects in files list

### 1.1: Reads Type

**File:** `src/stargazer/types/reads.py`

**Purpose:** Represent paired-end or single-end FASTQ files

**Attributes:**
- `sample_id: str` - Sample identifier
- `files: list[IpFile]` - List of FASTQ files (R1, R2 for paired-end)
- `read_group: dict[str, str] | None` - Optional read group metadata (ID, SM, LB, PL, PU)

**Methods:**
- `pinata_hydrate(sample_id: str, **filters) -> Reads` - Fetch reads from Pinata
- `fetch() -> Path` - Download all FASTQ files to cache
- `get_r1_path() -> Path` - Get path to R1 FASTQ
- `get_r2_path() -> Path` - Get path to R2 FASTQ (for paired-end)
- `add_files(file_paths: list[Path], keyvalues: dict) -> None` - Upload FASTQ files

**Metadata Schema:**
```python
keyvalues = {
    "type": "reads",
    "sample_id": "NA12829",
    "sequencing_platform": "ILLUMINA",  # optional
    "read_type": "paired"  # or "single"
}
```

**Test Checklist:**
- [ ] Test `pinata_hydrate()` with sample_id filter
- [ ] Test `fetch()` downloads all files
- [ ] Test `get_r1_path()` and `get_r2_path()`
- [ ] Test `add_files()` with metadata
- [ ] Test paired-end vs single-end reads
- [ ] Test with TP53 fixtures: `NA12829_TP53_R1.fq.gz`, `NA12829_TP53_R2.fq.gz`

**Implementation Order:**
1. Create TP53 FASTQ fixtures in Pinata (if not already)
2. Write `tests/test_reads.py` with all test cases
3. Implement `src/stargazer/types/reads.py`
4. Run tests until all pass

---

### 1.2: Alignment Type

**File:** `src/stargazer/types/alignment.py`

**Purpose:** Represent aligned BAM/CRAM files with optional index and metrics

**Attributes:**
- `sample_id: str` - Sample identifier
- `bam_name: str` - Name of the main BAM/CRAM file
- `files: list[IpFile]` - BAM file + optional BAI index + optional metrics
- `has_duplicates_marked: bool` - Whether duplicates are marked
- `is_sorted: bool` - Whether reads are coordinate sorted

**Methods:**
- `pinata_hydrate(sample_id: str, bam_name: str, **filters) -> Alignment` - Fetch alignment from Pinata
- `fetch() -> Path` - Download all files to cache
- `get_bam_path() -> Path` - Get path to BAM/CRAM file
- `get_bai_path() -> Path | None` - Get path to index file if present
- `add_files(file_paths: list[Path], keyvalues: dict) -> None` - Upload alignment files

**Metadata Schema:**
```python
keyvalues = {
    "type": "alignment",
    "sample_id": "NA12829",
    "tool": "fq2bam",
    "file_type": "bam",
    "sorted": "coordinate",
    "duplicates_marked": "true"
}
```

**Test Checklist:**
- [ ] Test `pinata_hydrate()` with sample_id filter
- [ ] Test `fetch()` downloads all files (BAM, BAI)
- [ ] Test `get_bam_path()` returns correct path
- [ ] Test `get_bai_path()` handles missing index
- [ ] Test `add_files()` with BAM + BAI
- [ ] Test metadata attributes (duplicates_marked, is_sorted)
- [ ] Generate TP53 BAM fixture (run fq2bam on TP53 FASTQ)

**Implementation Order:**
1. Generate TP53 BAM fixture using existing tools
2. Write `tests/test_alignment.py` with all test cases
3. Implement `src/stargazer/types/alignment.py`
4. Run tests until all pass

---

### 1.3: Variants Type

**File:** `src/stargazer/types/variants.py`

**Purpose:** Represent variant calls in VCF/GVCF format

**Attributes:**
- `sample_id: str` - Sample identifier
- `vcf_name: str` - Name of the VCF file
- `files: list[IpFile]` - VCF file + optional index (.tbi)
- `caller: str` - Variant caller used (deepvariant, haplotypecaller, etc.)
- `is_gvcf: bool` - Whether this is a GVCF

**Methods:**
- `pinata_hydrate(sample_id: str, **filters) -> Variants` - Fetch variants from Pinata
- `fetch() -> Path` - Download VCF and index to cache
- `get_vcf_path() -> Path` - Get path to VCF file
- `get_index_path() -> Path | None` - Get path to index if present
- `add_files(file_paths: list[Path], keyvalues: dict) -> None` - Upload VCF files

**Metadata Schema:**
```python
keyvalues = {
    "type": "variants",
    "sample_id": "NA12829",
    "caller": "deepvariant",  # or "haplotypecaller"
    "variant_type": "vcf",  # or "gvcf"
    "build": "GRCh38"
}
```

**Test Checklist:**
- [ ] Test `pinata_hydrate()` with sample_id and caller filters
- [ ] Test `fetch()` downloads VCF and index
- [ ] Test `get_vcf_path()` returns correct path
- [ ] Test `get_index_path()` handles missing index
- [ ] Test `add_files()` with VCF + index
- [ ] Test GVCF vs VCF distinction
- [ ] Generate TP53 VCF fixture

**Implementation Order:**
1. Generate TP53 VCF fixture (will come from variant caller tasks)
2. Write `tests/test_variants.py` with all test cases
3. Implement `src/stargazer/types/variants.py`
4. Run tests until all pass

---

## PHASE 2: Core Pipeline Tasks

### 2.1: fq2bam Task

**File:** `src/stargazer/tasks/fq2bam.py`

**Purpose:** Align FASTQ reads to reference, sort, and mark duplicates

**Reference:** `context/tool_refs/fq2bam.md`

**Inputs:**
- `reads: Reads` - Input FASTQ files
- `ref: Reference` - Reference genome with BWA index and FAI
- `read_group: dict[str, str] | None` - Optional read group override

**Outputs:**
- `alignment: Alignment` - Sorted, duplicate-marked BAM

**Command Template:**
```bash
pbrun fq2bam \
    --ref <ref.fasta> \
    --in-fq <R1.fastq.gz> <R2.fastq.gz> ["@RG\t..."] \
    --out-bam <output.bam> \
    --bwa-options="-K 10000000"
```

**Implementation Details:**
1. Fetch all input files (reads, reference) to cache
2. Build read group string if provided or use defaults (SM=sample_id)
3. Construct pbrun command with all paths
4. Execute via `_run()` utility
5. Create Alignment object with output BAM as an IpFile
6. Return Alignment object

**Metadata for Output BAM:**
```python
keyvalues = {
    "type": "alignment",
    "sample_id": reads.sample_id,
    "tool": "fq2bam",
    "file_type": "bam",
    "sorted": "coordinate",
    "duplicates_marked": "true"
}
```

**Test Checklist:**
- [ ] Generate expected TP53 BAM output (run fq2bam manually on TP53 fixtures)
- [ ] Test fq2bam with custom read group metadata
- [ ] Test fq2bam with default read group (auto-generated)
- [ ] Verify output BAM is coordinate sorted
- [ ] Verify duplicates are marked
- [ ] Test idempotency (running twice doesn't fail)
- [ ] Test error handling (missing reference, missing reads)

**Implementation Order:**
1. Generate TP53 BAM fixture by running fq2bam manually
2. Write `tests/test_fq2bam.py` with all test cases
3. Implement `src/stargazer/tasks/fq2bam.py`
4. Run tests until all pass

---

### 2.2: deepvariant Task

**File:** `src/stargazer/tasks/deepvariant.py`

**Purpose:** Call variants from aligned BAM using DeepVariant neural network

**Reference:** `context/tool_refs/deepvariant_germline.md`

**Note:** For MVP, we're implementing standalone DeepVariant, NOT the combined deepvariant_germline workflow (which includes alignment). We already have fq2bam for alignment.

**Inputs:**
- `alignment: Alignment` - Input BAM file (sorted, duplicate-marked)
- `ref: Reference` - Reference genome
- `output_gvcf: bool = False` - Whether to output GVCF format

**Outputs:**
- `variants: Variants` - VCF/GVCF file with variant calls

**Command Template:**
```bash
# Note: If using standalone deepvariant (not deepvariant_germline):
# We need to use `pbrun deepvariant` which takes a BAM as input
# OR use the full `deepvariant_germline` with --in-bam option

# Check Parabricks docs - likely need:
pbrun deepvariant \
    --ref <ref.fasta> \
    --in-bam <input.bam> \
    --out-variants <output.vcf> \
    [--gvcf]  # if output_gvcf=True
```

**Implementation Details:**
1. Fetch alignment and reference files to cache
2. Construct pbrun deepvariant command
3. Execute via `_run()` utility
4. Create Variants object with output VCF
5. Handle GVCF vs VCF output

**Metadata for Output VCF:**
```python
keyvalues = {
    "type": "variants",
    "sample_id": alignment.sample_id,
    "caller": "deepvariant",
    "variant_type": "gvcf" if output_gvcf else "vcf",
    "build": ref.ref_name.split("_")[0]  # e.g., "GRCh38"
}
```

**Test Checklist:**
- [ ] Generate expected TP53 VCF output (run deepvariant manually on TP53 BAM)
- [ ] Test deepvariant with VCF output
- [ ] Test deepvariant with GVCF output
- [ ] Verify VCF contains variants for TP53 region
- [ ] Verify VCF format is valid (can be parsed by vcftools/bcftools)
- [ ] Test idempotency
- [ ] Test error handling (missing BAM, missing reference)

**Implementation Order:**
1. Generate TP53 VCF fixture by running deepvariant manually on TP53 BAM
2. Write `tests/test_deepvariant.py` with all test cases
3. Implement `src/stargazer/tasks/deepvariant.py`
4. Run tests until all pass

---

### 2.3: haplotypecaller Task

**File:** `src/stargazer/tasks/haplotypecaller.py`

**Purpose:** Call variants from aligned BAM using GATK HaplotypeCaller

**Reference:** `context/tool_refs/haplotypecaller.md`

**Inputs:**
- `alignment: Alignment` - Input BAM file (sorted, duplicate-marked)
- `ref: Reference` - Reference genome
- `output_gvcf: bool = False` - Whether to output GVCF format

**Outputs:**
- `variants: Variants` - VCF/GVCF file with variant calls

**Command Template:**
```bash
pbrun haplotypecaller \
    --ref <ref.fasta> \
    --in-bam <input.bam> \
    --out-variants <output.vcf> \
    [--gvcf]  # if output_gvcf=True
```

**Implementation Details:**
1. Fetch alignment and reference to cache
2. Construct pbrun haplotypecaller command
3. Execute via `_run()` utility
4. Create Variants object with output VCF

**Metadata for Output VCF:**
```python
keyvalues = {
    "type": "variants",
    "sample_id": alignment.sample_id,
    "caller": "haplotypecaller",
    "variant_type": "gvcf" if output_gvcf else "vcf",
    "build": ref.ref_name.split("_")[0]
}
```

**Test Checklist:**
- [ ] Generate expected TP53 VCF output (run haplotypecaller manually on TP53 BAM)
- [ ] Test haplotypecaller with VCF output
- [ ] Test haplotypecaller with GVCF output
- [ ] Verify VCF contains variants for TP53 region
- [ ] Verify VCF format is valid
- [ ] Test idempotency
- [ ] Test error handling

**Implementation Order:**
1. Generate TP53 VCF fixture by running haplotypecaller manually on TP53 BAM
2. Write `tests/test_haplotypecaller.py` with all test cases
3. Implement `src/stargazer/tasks/haplotypecaller.py`
4. Run tests until all pass

---

## PHASE 3: Complete MVP Workflow

### 3.1: Whole Genome Germline Small Variants Workflow

**File:** `src/stargazer/workflows/parabricks.py` (update existing file)

**Purpose:** End-to-end workflow from FASTQ to VCF(s)

**Workflow Name:** `wgs_germline_snv`

**Inputs:**
- `sample_id: str` - Sample identifier for querying reads
- `ref_name: str` - Reference genome name (e.g., "GRCh38_TP53.fa")
- `run_deepvariant: bool = True` - Whether to run DeepVariant caller
- `run_haplotypecaller: bool = True` - Whether to run HaplotypeCaller
- `output_gvcf: bool = False` - Whether to output GVCF format

**Outputs:**
- `alignment: Alignment` - Final aligned BAM
- `deepvariant_vcf: Variants | None` - DeepVariant results (if enabled)
- `haplotypecaller_vcf: Variants | None` - HaplotypeCaller results (if enabled)

**Workflow Steps:**
```python
@pb_env.task
async def wgs_germline_snv(
    sample_id: str,
    ref_name: str,
    run_deepvariant: bool = True,
    run_haplotypecaller: bool = True,
    output_gvcf: bool = False,
) -> tuple[Alignment, Variants | None, Variants | None]:
    """
    Complete whole genome germline small variant calling workflow.

    Steps:
    1. Hydrate reference genome from Pinata
    2. Index reference (samtools faidx + bwa index)
    3. Hydrate reads (FASTQ) from Pinata
    4. Run fq2bam (alignment + sorting + markdups)
    5. Run DeepVariant (if enabled)
    6. Run HaplotypeCaller (if enabled)

    Returns:
        Tuple of (alignment, deepvariant_vcf, haplotypecaller_vcf)
    """
    # Step 1-2: Reference preparation
    ref = await Reference.pinata_hydrate(ref_name=ref_name)
    ref = await samtools_faidx(ref)
    ref = await bwa_index(ref)

    # Step 3: Fetch reads
    reads = await Reads.pinata_hydrate(sample_id=sample_id)

    # Step 4: Alignment
    alignment = await fq2bam(
        reads=reads,
        ref=ref
    )

    # Step 5-6: Variant calling (can run in parallel)
    deepvariant_vcf = None
    haplotypecaller_vcf = None

    if run_deepvariant:
        deepvariant_vcf = await deepvariant(
            alignment=alignment,
            ref=ref,
            output_gvcf=output_gvcf
        )

    if run_haplotypecaller:
        haplotypecaller_vcf = await haplotypecaller(
            alignment=alignment,
            ref=ref,
            output_gvcf=output_gvcf
        )

    return alignment, deepvariant_vcf, haplotypecaller_vcf
```

**Test Checklist:**
- [ ] Test workflow with both callers enabled
- [ ] Test workflow with only DeepVariant
- [ ] Test workflow with only HaplotypeCaller
- [ ] Test workflow with GVCF output
- [ ] Test workflow with VCF output
- [ ] Verify all outputs are created and valid
- [ ] Verify workflow can be run in local mode
- [ ] Verify workflow can be submitted to Flyte cluster

**Implementation Order:**
1. Ensure all previous phases (types and tasks) are complete
2. Write `tests/test_workflow.py` with comprehensive test cases
3. Update `src/stargazer/workflows/parabricks.py`
4. Run integration tests
5. Test on actual Flyte cluster (if available)

---

## PHASE 4: Documentation and Polish

### 4.1: Update Type Annotations

**Task Checklist:**
- [ ] Ensure all types are exported in `src/stargazer/types/__init__.py`
- [ ] Ensure all tasks are exported in `src/stargazer/tasks/__init__.py`
- [ ] Add proper type hints throughout codebase
- [ ] Add docstrings to all public methods
- [ ] Verify mypy/pyright type checking passes

### 4.2: README and Examples

**File:** `README.md`

**Content:**
- [ ] Project overview and purpose
- [ ] Architecture diagram (types and tasks)
- [ ] Installation instructions
- [ ] Quick start example using TP53 fixtures
- [ ] Running tests
- [ ] Deploying to Flyte cluster
- [ ] Pinata setup and configuration

**File:** `examples/run_tp53_workflow.py`

**Content:**
- [ ] Complete example running TP53 workflow locally
- [ ] Shows how to use workflow outputs
- [ ] Demonstrates querying results from Pinata

### 4.3: CI/CD

**File:** `.github/workflows/test.yml`

**Content:**
- [ ] Run pytest on all tests
- [ ] Run type checking (mypy)
- [ ] Run linting (ruff)
- [ ] Test with multiple Python versions (3.11, 3.12)

---

## Fixture Generation Guide

For each phase, AI agents should generate test fixtures BEFORE implementation:

### Reference Fixtures (Already Complete)
- `GRCh38_TP53.fa` - TP53 region reference
- `GRCh38_TP53.fa.fai` - FASTA index
- `GRCh38_TP53.fa.{amb,ann,bwt,pac,sa}` - BWA indices

### Reads Fixtures (Already Complete)
- `NA12829_TP53_R1.fq.gz` - Paired-end R1
- `NA12829_TP53_R2.fq.gz` - Paired-end R2

### Alignment Fixture (TODO: Phase 2.1)
```bash
# Run fq2bam on TP53 fixtures (requires GPU or CPU fallback)
pbrun fq2bam \
    --ref tests/fixtures/GRCh38_TP53.fa \
    --in-fq tests/fixtures/NA12829_TP53_R1.fq.gz tests/fixtures/NA12829_TP53_R2.fq.gz \
    --out-bam tests/fixtures/NA12829_TP53.bam
```

### Variant Fixtures (TODO: Phase 2.2, 2.3)
```bash
# DeepVariant
pbrun deepvariant \
    --ref tests/fixtures/GRCh38_TP53.fa \
    --in-bam tests/fixtures/NA12829_TP53.bam \
    --out-variants tests/fixtures/NA12829_TP53_deepvariant.vcf

# HaplotypeCaller
pbrun haplotypecaller \
    --ref tests/fixtures/GRCh38_TP53.fa \
    --in-bam tests/fixtures/NA12829_TP53.bam \
    --out-variants tests/fixtures/NA12829_TP53_haplotypecaller.vcf
```

---

## Success Criteria

The MVP is complete when:

1. ✅ All 3 core types are implemented and tested (Reads, Alignment, Variants)
2. ✅ All 3 core tasks are implemented and tested (fq2bam, deepvariant, haplotypecaller)
3. ✅ Complete workflow runs end-to-end (FASTQ → VCF)
4. ✅ All tests pass with TP53 fixtures
5. ✅ Workflow can run in local mode (`flyte.with_runcontext(mode="local")`)
6. ✅ All outputs can be queried from Pinata via metadata
7. ✅ README documentation is complete
8. ✅ CI/CD pipeline is functional

---

## AI Agent Checklist Format

When working on a phase, AI agents should:

1. **Before starting implementation:**
   - [ ] Read relevant context files (tool_refs/, type_spec.md)
   - [ ] Study existing implementations (Reference type, samtools/bwa tasks)
   - [ ] Generate or verify test fixtures exist
   - [ ] Create comprehensive test file

2. **During implementation:**
   - [ ] Follow architectural patterns from existing code
   - [ ] Use proper type hints
   - [ ] Add docstrings to all public methods
   - [ ] Handle errors appropriately
   - [ ] Use metadata schema consistently

3. **After implementation:**
   - [ ] Run tests and verify all pass
   - [ ] Run type checker (mypy/pyright)
   - [ ] Run linter (ruff)
   - [ ] Update relevant documentation
   - [ ] Mark tasks complete in this roadmap

---

## Notes for AI Agents

1. **Always test first**: Write tests before implementation
2. **Use TP53 fixtures**: All tests should use small TP53 region data for speed
3. **Follow existing patterns**: Look at Reference type and existing tasks as templates
4. **Metadata is key**: Every file uploaded to Pinata needs proper keyvalues
5. **One task per tool**: Don't combine multiple Parabricks tools in one task
6. **Error handling**: Always validate inputs and provide clear error messages
7. **Documentation**: Every public method needs a docstring with examples
8. **Idempotency**: Tasks should be idempotent where possible

---

## Appendix: Command Reference

### Useful Commands

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_fq2bam.py -v

# Run tests with coverage
pytest --cov=src/stargazer --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/ tests/

# Format code
ruff format src/ tests/

# Run workflow locally
python -m src.stargazer.workflows.parabricks

# Check Flyte configuration
flyte config list
```

### Environment Variables

```bash
# Pinata API configuration
export PINATA_JWT="your-jwt-token"

# Local-only mode (no IPFS uploads)
export STARGAZER_LOCAL_ONLY=1

# Flyte configuration
export FLYTE_CONFIG_FILE="~/.flyte/config.yaml"
```

---

**End of Roadmap**

This roadmap provides a clear, step-by-step path to implementing the Stargazer MVP. AI agents should work through phases sequentially, ensuring all tests pass before moving to the next phase.
