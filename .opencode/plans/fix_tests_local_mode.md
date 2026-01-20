# Fix Tests for Local Mode Plan

## Overview

Update all tests to use the new local mode hydration function and renamed `local_dir` property (formerly `cache_dir`). This aligns the test suite with the local filesystem implementation described in `local_filesystem.md`.

## Current State

- Tests reference `default_client.cache_dir` which no longer exists
- Tests create mock files directly in the cache directory
- Tests don't use the new TinyDB-backed metadata storage
- Source code still has `pinata_hydrate` references that should use the new `hydrate` task
- Tests fail because `PinataClient` no longer has a `cache_dir` attribute (renamed to `local_dir`)

## Target State

- All tests use `default_client.local_dir` instead of `default_client.cache_dir`
- Tests that mock local files properly register metadata in TinyDB
- Tests work in local-only mode without network requirements
- Source code uses the general `hydrate` task from `stargazer.tasks.hydrate`

## Implementation Plan

### Phase 1: Simple Rename - `cache_dir` to `local_dir`

Update all test files that reference `cache_dir` to use `local_dir` instead.

**Files to update:**

| File | Lines to Change |
|------|-----------------|
| `tests/test_samtools.py` | 29, 30, 95, 99, 100 |
| `tests/test_reads.py` | 27, 28, 29, 60, 63, 64, 86, 87, 88, 143, 144 |
| `tests/test_variants.py` | 33, 34, 35, 71, 74, 75, 105, 106, 152, 153, 154, 212, 213 |
| `tests/test_reference.py` | 108, 113, 114 |
| `tests/test_alignment.py` | 27, 28, 29, 66, 69, 70, 92, 93, 133, 134, 135, 186, 187 |
| `tests/test_bwa.py` | 29, 30, 107, 111, 132, 164 |
| `tests/test_germline_workflow.py` | 33, 34, 75, 76, 77, 124, 125 |
| `tests/test_baserecalibrator.py` | 25, 26, 56, 57, 92, 94 |
| `tests/test_genotypegvcf.py` | 25, 26, 70, 71, 108, 112 |
| `tests/test_combinegvcfs.py` | 25, 26, 70, 71, 106, 119, 237, 241 |
| `tests/test_mergebamalignment.py` | 28, 29, 58, 59, 95, 98, 100 |
| `tests/test_sortsam.py` | 25, 26, 54, 55, 90, 92 |
| `tests/test_applybqsr.py` | 25, 26, 56, 57, 88, 89, 131, 133, 135 |
| `tests/test_markduplicates.py` | 25, 26, 55, 56, 91, 93 |

**Change pattern:**
```python
# Before
default_client.cache_dir.mkdir(parents=True, exist_ok=True)
cached_file = default_client.cache_dir / test_cid

# After
default_client.local_dir.mkdir(parents=True, exist_ok=True)
cached_file = default_client.local_dir / test_cid
```

### Phase 2: Update Helper Functions with `cache_dir` Parameter

Some test files have helper functions that accept `cache_dir` as a parameter. Update these function signatures and calls.

**Files with helper functions:**

| File | Helper Function | Lines |
|------|-----------------|-------|
| `tests/test_baserecalibrator.py` | `create_mock_alignment()`, `create_mock_reference()` | 17, 49 |
| `tests/test_genotypegvcf.py` | `create_mock_variants()`, `create_mock_reference()` | 17, 63 |
| `tests/test_combinegvcfs.py` | `create_mock_variants()`, `create_mock_reference()` | 17, 63 |
| `tests/test_mergebamalignment.py` | `create_mock_alignment()`, `create_mock_reference()` | 17, 51 |
| `tests/test_sortsam.py` | `create_mock_alignment()`, `create_mock_reference()` | 17, 47 |
| `tests/test_applybqsr.py` | `create_mock_alignment()`, `create_mock_reference()`, `create_mock_recal_report()` | 17, 49, 80 |
| `tests/test_markduplicates.py` | `create_mock_alignment()`, `create_mock_reference()` | 17, 48 |

**Change pattern:**
```python
# Before
def create_mock_alignment(
    cache_dir: Path, sample_id: str, test_cid: str
) -> tuple[Path, Alignment, IpFile]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    bam_path = cache_dir / test_cid

# After
def create_mock_alignment(
    local_dir: Path, sample_id: str, test_cid: str
) -> tuple[Path, Alignment, IpFile]:
    local_dir.mkdir(parents=True, exist_ok=True)
    bam_path = local_dir / test_cid
```

### Phase 3: Update Source Code `pinata_hydrate` to `hydrate`

Replace deprecated `pinata_hydrate` class method calls with the general `hydrate` task.

**Files to update:**

| File | Lines | Current Usage |
|------|-------|---------------|
| `src/stargazer/workflows/parabricks.py` | 67, 72 | `Reference.pinata_hydrate()`, `Reads.pinata_hydrate()` |
| `src/stargazer/workflows/gatk_data_preprocessing.py` | 56, 121 | `Reference.pinata_hydrate()`, `Reads.pinata_hydrate()` |
| `src/stargazer/workflows/germline_short_variant_discovery.py` | 63, 101 | `Reference.pinata_hydrate()`, `Reads.pinata_hydrate()` |
| `src/stargazer/tasks/bwa.py` | 122 | `Reads.pinata_hydrate()` (docstring example) |
| `src/stargazer/tasks/parabricks/fq2bam.py` | 33, 36 | `Reference.pinata_hydrate()`, `Reads.pinata_hydrate()` (docstring example) |

**Change pattern:**
```python
# Before
from stargazer.types import Reference, Reads

ref = await Reference.pinata_hydrate(ref_name=ref_name)
reads = await Reads.pinata_hydrate(sample_id=sample_id)

# After
from stargazer.tasks import hydrate

refs = await hydrate({"type": "reference", "build": ref_name})
ref = refs[0] if refs else None

reads_list = await hydrate({"type": "reads", "sample_id": sample_id})
reads = reads_list[0] if reads_list else None
```

### Phase 4: Update Agent Documentation

Update agent markdown files that contain stale `cache_dir` or `pinata_hydrate` references.

**Files to update:**

| File | Reference | Action |
|------|-----------|--------|
| `.opencode/plans/keyvalue_components.md` | `cache_dir` references | Update to `local_dir` |
| `.opencode/agent/code-review.md` | `pinata_hydrate` | Update to `hydrate` |
| `.opencode/agent/workflow.md` | `pinata_hydrate` | Update to `hydrate` |

### Phase 5: Run Tests and Verify

1. Run `pytest tests/` to identify any remaining issues
2. Fix any test failures related to TinyDB or local mode behavior
3. Verify tests pass in local-only mode (STARGAZER_LOCAL_ONLY=1)

## File Changes Summary

| File | Changes |
|------|---------|
| `tests/test_samtools.py` | `cache_dir` → `local_dir` |
| `tests/test_reads.py` | `cache_dir` → `local_dir` |
| `tests/test_variants.py` | `cache_dir` → `local_dir` |
| `tests/test_reference.py` | `cache_dir` → `local_dir` |
| `tests/test_alignment.py` | `cache_dir` → `local_dir` |
| `tests/test_bwa.py` | `cache_dir` → `local_dir` |
| `tests/test_germline_workflow.py` | `cache_dir` → `local_dir` |
| `tests/test_baserecalibrator.py` | `cache_dir` → `local_dir` + helper functions |
| `tests/test_genotypegvcf.py` | `cache_dir` → `local_dir` + helper functions |
| `tests/test_combinegvcfs.py` | `cache_dir` → `local_dir` + helper functions |
| `tests/test_mergebamalignment.py` | `cache_dir` → `local_dir` + helper functions |
| `tests/test_sortsam.py` | `cache_dir` → `local_dir` + helper functions |
| `tests/test_applybqsr.py` | `cache_dir` → `local_dir` + helper functions |
| `tests/test_markduplicates.py` | `cache_dir` → `local_dir` + helper functions |
| `src/stargazer/workflows/parabricks.py` | `pinata_hydrate` → `hydrate` |
| `src/stargazer/workflows/gatk_data_preprocessing.py` | `pinata_hydrate` → `hydrate` |
| `src/stargazer/workflows/germline_short_variant_discovery.py` | `pinata_hydrate` → `hydrate` |
| `src/stargazer/tasks/bwa.py` | Update docstring example |
| `src/stargazer/tasks/parabricks/fq2bam.py` | Update docstring example |
| `.opencode/plans/keyvalue_components.md` | `cache_dir` → `local_dir` |
| `.opencode/agent/code-review.md` | `pinata_hydrate` → `hydrate` |
| `.opencode/agent/workflow.md` | `pinata_hydrate` → `hydrate` |

## Design Decisions

1. **Simple find-replace for `cache_dir`**: The rename from `cache_dir` to `local_dir` is a straightforward refactor with no behavioral change. Apply globally.

2. **Keep helper function signatures consistent**: Rename the parameter from `cache_dir` to `local_dir` in all helper functions to maintain consistency.

3. **`hydrate` task over class methods**: The general `hydrate` task is the new pattern. It queries by keyvalues and returns typed instances. Class methods like `pinata_hydrate` should be deprecated.

4. **Local-only mode as default for tests**: Tests should work in local-only mode by default. Network-dependent tests should be skipped when `PINATA_JWT` is not set.

5. **Update documentation**: Keep agent docs in sync with implementation to avoid confusion during development.

## Execution Order

1. **Phase 1** (simple rename) - Safe, mechanical changes
2. **Phase 2** (helper functions) - Still mechanical, slightly more involved
3. **Phase 3** (source code) - Requires understanding of `hydrate` task behavior
4. **Phase 4** (documentation) - Low priority, can be done last
5. **Phase 5** (verification) - Run tests to confirm all changes work together
