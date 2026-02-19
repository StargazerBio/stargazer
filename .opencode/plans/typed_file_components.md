# Typed File Components: Central Schema for Stargazer Types

## Context

Metadata for stored files is defined implicitly in 4+ places: `update_*()` method bodies, `@property` accessors, fixture data (`build_local_db.py`), and inline keyvalue dicts in tasks. There is no central definition of what metadata a given file component carries, what values are valid, or how they serialize. This makes drift easy and validation impossible.

We're adding typed file component dataclasses as the single source of truth for per-file metadata. Each component declares its metadata fields with proper Python types. The containers (Reference, Alignment, Reads, Variants) become thin compositions of these components. The flat `dict[str, str]` keyvalues become a serialization detail handled by `to_keyvalues()`/`from_keyvalues()` on the base class.

## Phase 1: FileComponent Base Class

**New file: `src/stargazer/types/base.py`**

```python
@dataclass
class FileComponent:
    TYPE: ClassVar[str]       # e.g. "alignment" — included in keyvalues, not a constructor arg
    COMPONENT: ClassVar[str]  # e.g. "alignment" — included in keyvalues, not a constructor arg
    ipfile: IpFile | None = field(default=None, repr=False)
```

Methods:
- `to_keyvalues() -> dict[str, str]` — Reflects over dataclass fields (skipping `ipfile`). Prepends `type`/`component`. Conversions: `bool` -> `"true"`/`"false"`, `int` -> `str()`, `list[str]` -> `",".join()`, `None` -> skip, everything else passthrough. Field name = keyvalue key (1:1, no renaming).
- `from_keyvalues(cls, kv: dict[str, str], ipfile: IpFile | None = None) -> Self` — Reverse: introspects field type annotations, converts string values back. Attaches ipfile.
- `to_dict() -> dict` — Metadata fields + `ipfile.to_dict()` if present.
- `from_dict(cls, data: dict) -> Self` — Reconstructs from dict (extracts ipfile data, passes metadata to constructor).

Standalone helper (same module):
```python
async def upload_component(component: FileComponent, path: Path) -> FileComponent:
    """Upload file, attach resulting IpFile to the component."""
    ipfile = await default_client.upload_file(path, keyvalues=component.to_keyvalues())
    component.ipfile = ipfile
    return component
```

**Tests first: `tests/unit/test_file_component.py`**
- `to_keyvalues()` round-trips all supported types (str, bool, int, list[str], None-skip, Literal)
- TYPE/COMPONENT appear in output but `ipfile` does not
- `from_keyvalues()` correctly reverses bool/int/list conversions
- `to_dict()`/`from_dict()` round-trip with and without ipfile

## Phase 2: File Component Definitions

Define in the existing type modules, above the container classes.

### `src/stargazer/types/reference.py`

| Class | TYPE | COMPONENT | Fields |
|-------|------|-----------|--------|
| `Fasta` | reference | fasta | `build: str` |
| `Faidx` | reference | faidx | `build: str`, `tool: str \| None` |
| `SequenceDict` | reference | sequence_dictionary | `build: str`, `tool: str \| None` |
| `AlignerIndex` | reference | aligner_index | `build: str`, `aligner: str` |

### `src/stargazer/types/alignment.py`

| Class | TYPE | COMPONENT | Fields |
|-------|------|-----------|--------|
| `AlignmentFile` | alignment | alignment | `sample_id: str`, `format: str \| None`, `sorted: str \| None`, `duplicates_marked: bool`, `bqsr_applied: bool`, `tool: str \| None` |
| `AlignmentIndex` | alignment | index | `sample_id: str` |

### `src/stargazer/types/reads.py`

| Class | TYPE | COMPONENT | Fields |
|-------|------|-----------|--------|
| `R1File` | reads | r1 | `sample_id: str`, `sequencing_platform: str \| None` |
| `R2File` | reads | r2 | `sample_id: str`, `sequencing_platform: str \| None` |

Two classes (not one with variable COMPONENT) so COMPONENT stays a ClassVar.

### `src/stargazer/types/variants.py`

| Class | TYPE | COMPONENT | Fields |
|-------|------|-----------|--------|
| `VariantsFile` | variants | vcf | `sample_id: str`, `caller: str \| None`, `variant_type: str \| None`, `build: str \| None`, `sample_count: int \| None`, `source_samples: list[str] \| None` |
| `VariantsIndex` | variants | index | `sample_id: str` |

**Tests: one test per component class verifying `to_keyvalues()` output and round-trip.**

## Phase 3: Refactor Container Types

Each container becomes thin composition. Remove all `update_*()` methods and property proxies. Keep `fetch()` (iterates components, downloads their `ipfile`), `to_dict()`, `from_dict()`.

### Reference
```python
@dataclass
class Reference:
    build: str
    fasta: Fasta | None = None
    faidx: Faidx | None = None
    sequence_dictionary: SequenceDict | None = None
    aligner_index: list[AlignerIndex] = field(default_factory=list)
```
Removed: `update_fasta()`, `update_faidx()`, `update_sequence_dictionary()`, `update_aligner_index()`

### Alignment
```python
@dataclass
class Alignment:
    sample_id: str
    alignment: AlignmentFile | None = None
    index: AlignmentIndex | None = None
```
Removed: `update_alignment()`, `update_index()`, `is_sorted`, `has_duplicates_marked`, `has_bqsr_applied`

Callers change:
- `alignment.is_sorted` -> `alignment.alignment.sorted == "coordinate"`
- `alignment.has_duplicates_marked` -> `alignment.alignment.duplicates_marked`
- `alignment.has_bqsr_applied` -> `alignment.alignment.bqsr_applied`

### Reads
```python
@dataclass
class Reads:
    sample_id: str
    r1: R1File | None = None
    r2: R2File | None = None
    read_group: dict[str, str] | None = None

    @property
    def is_paired(self) -> bool:  # stays — derived from container, not a single file
        return self.r1 is not None and self.r2 is not None
```
Removed: `update_r1()`, `update_r2()`

### Variants
```python
@dataclass
class Variants:
    sample_id: str
    vcf: VariantsFile | None = None
    index: VariantsIndex | None = None
```
Removed: `update_vcf()`, `update_index()`, `caller`, `is_gvcf`, `is_multi_sample`, `source_samples`

Callers change:
- `variants.caller` -> `variants.vcf.caller`
- `variants.is_gvcf` -> `variants.vcf.variant_type == "gvcf"`
- `variants.source_samples` -> `variants.vcf.source_samples or [variants.sample_id]`

**Update `src/stargazer/types/__init__.py`** — export all file component classes.

## Phase 4: Update Tasks

Every task that called `container.update_*()` changes to construct a typed component + `upload_component()`.

### Pattern (sort_sam as reference example)

Before:
```python
sorted_alignment = Alignment(sample_id=alignment.sample_id)
await sorted_alignment.update_alignment(
    output_bam, format="bam", is_sorted=(sort_order == "coordinate"),
    duplicates_marked=alignment.has_duplicates_marked,
    bqsr_applied=alignment.has_bqsr_applied, tool="gatk_sort_sam",
)
await sorted_alignment.update_index(bam_index)
```

After:
```python
from stargazer.types.alignment import AlignmentFile, AlignmentIndex
from stargazer.types.base import upload_component

bam = AlignmentFile(
    sample_id=alignment.sample_id, format="bam",
    sorted="coordinate" if sort_order == "coordinate" else sort_order,
    duplicates_marked=alignment.alignment.duplicates_marked,
    bqsr_applied=alignment.alignment.bqsr_applied,
    tool="gatk_sort_sam",
)
bam = await upload_component(bam, output_bam)
idx = await upload_component(AlignmentIndex(sample_id=alignment.sample_id), bam_index)
sorted_alignment = Alignment(sample_id=alignment.sample_id, alignment=bam, index=idx)
```

### Tasks to update (working — mechanical migration)

| Task file | Changes |
|-----------|---------|
| `tasks/general/samtools.py` | `ref.update_faidx()` -> `Faidx` + `upload_component` |
| `tasks/gatk/create_sequence_dictionary.py` | `ref.update_sequence_dictionary()` -> `SequenceDict` + `upload_component` |
| `tasks/general/bwa.py` (`bwa_index`) | `ref.update_aligner_index()` -> `AlignerIndex` + `upload_component` |
| `tasks/general/bwa.py` (`bwa_mem`) | `alignment.update_alignment()` -> `AlignmentFile` + `upload_component` |
| `tasks/gatk/sort_sam.py` | As shown above |
| `tasks/gatk/mark_duplicates.py` | Same pattern; metrics file stays as raw `upload_file()` |
| `tasks/gatk/merge_bam_alignment.py` | Same pattern |
| `tasks/gatk/apply_bqsr.py` | Same pattern |
| `tasks/gatk/base_recalibrator.py` | Raw `upload_file()` stays for now (returns `IpFile`) |
| `tasks/gatk/combine_gvcfs.py` | `variants.update_vcf()` -> `VariantsFile` + `upload_component` |
| `tasks/gatk/genotype_gvcf.py` | Same; also update `gvcf.source_samples` -> `gvcf.vcf.source_samples` |

### Tasks to rewrite (already broken — reference nonexistent methods)

| Task file | Broken references |
|-----------|------------------|
| `tasks/gatk/variant_recalibrator.py` | `vcf.vcf_name`, `vcf.get_vcf_path()`, `ref.get_ref_path()` |
| `tasks/gatk/apply_vqsr.py` | `vcf.vcf_name`, `vcf.get_vcf_path()`, `ref.get_ref_path()`, `vcf.files`, `variants.add_files()` |
| `tasks/gatk/genomics_db_import.py` | `gvcf.vcf_name`, `gvcf.get_vcf_path()` |

These get rewritten to follow the same component pattern. Replace `vcf.get_vcf_path()` with `vcf.vcf.ipfile.local_path`, `ref.get_ref_path()` with `ref.fasta.ipfile.local_path`, etc.

## Phase 5: Update Hydrate, Marshal, Serialization

### `tasks/general/hydrate.py`
- `TYPE_REGISTRY` now maps `(type, component)` -> `FileComponent subclass`
- Instead of `setattr(instance, field_name, ipfile)`, construct the typed component via `ComponentClass.from_keyvalues(ipfile.keyvalues, ipfile=ipfile)` and assign to the container field

### `marshal.py`
- Add all file component classes to `_FROM_DICT_TYPES`
- `marshal_output` already checks `hasattr(value, "to_dict")` — works automatically

### Serialization tests (`tests/types/test_serialization.py`)
- Container `to_dict()` output shape changes: components are now nested component dicts (with metadata fields) instead of raw IpFile dicts
- Remove assertions like `data["is_sorted"]` at the container level; these fields now live inside `data["alignment"]`

### Existing type tests (`tests/types/test_alignment.py` etc.)
- Tests that construct `Alignment(alignment=IpFile(...))` change to `Alignment(alignment=AlignmentFile(..., ipfile=IpFile(...)))`
- Tests for property accessors (`alignment.has_duplicates_marked`) change to field access (`alignment.alignment.duplicates_marked`)
- `test_alignment_update_components` rewrites to use `upload_component()`

## Implementation Order

1. `base.py` + `tests/unit/test_file_component.py` — foundation, test it works
2. File components in all 4 type modules — define the schema
3. Container refactoring — strip to composition
4. Task updates (working tasks first, broken tasks last) — one at a time, run tests after each
5. Hydrate + marshal updates
6. Test suite cleanup + full run

## Files Modified

| File | Action |
|------|--------|
| `src/stargazer/types/base.py` | **New** — FileComponent base, upload_component |
| `src/stargazer/types/reference.py` | Add Fasta, Faidx, SequenceDict, AlignerIndex; strip Reference |
| `src/stargazer/types/alignment.py` | Add AlignmentFile, AlignmentIndex; strip Alignment |
| `src/stargazer/types/reads.py` | Add R1File, R2File; strip Reads |
| `src/stargazer/types/variants.py` | Add VariantsFile, VariantsIndex; strip Variants |
| `src/stargazer/types/__init__.py` | Export new classes |
| `src/stargazer/tasks/general/samtools.py` | Use Faidx + upload_component |
| `src/stargazer/tasks/general/bwa.py` | Use AlignerIndex, AlignmentFile + upload_component |
| `src/stargazer/tasks/gatk/create_sequence_dictionary.py` | Use SequenceDict + upload_component |
| `src/stargazer/tasks/gatk/sort_sam.py` | Use AlignmentFile, AlignmentIndex + upload_component |
| `src/stargazer/tasks/gatk/mark_duplicates.py` | Use AlignmentFile, AlignmentIndex + upload_component |
| `src/stargazer/tasks/gatk/merge_bam_alignment.py` | Use AlignmentFile, AlignmentIndex + upload_component |
| `src/stargazer/tasks/gatk/apply_bqsr.py` | Use AlignmentFile + upload_component |
| `src/stargazer/tasks/gatk/combine_gvcfs.py` | Use VariantsFile + upload_component |
| `src/stargazer/tasks/gatk/genotype_gvcf.py` | Use VariantsFile + upload_component |
| `src/stargazer/tasks/gatk/variant_recalibrator.py` | Rewrite (broken) |
| `src/stargazer/tasks/gatk/apply_vqsr.py` | Rewrite (broken) |
| `src/stargazer/tasks/gatk/genomics_db_import.py` | Rewrite (broken) |
| `src/stargazer/tasks/general/hydrate.py` | Construct typed components from keyvalues |
| `src/stargazer/marshal.py` | Add component classes to _FROM_DICT_TYPES |
| `tests/unit/test_file_component.py` | **New** — base class tests |
| `tests/types/test_*.py` | Update for new component types |
| `tests/unit/test_marshal.py` | Update for new serialization shape |

## Verification

```bash
# After each phase:
cd /home/coder/stargazer && uv run pytest tests/unit/ tests/types/ -v

# Full suite after all phases:
cd /home/coder/stargazer && uv run pytest tests/ -v
```
