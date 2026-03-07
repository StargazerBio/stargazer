# Filesystem & Type System Specification

## Design Goals

Every file in Stargazer carries structured keyvalue metadata that describes its role, enabling:

- **Consistency**: All tools produce and consume files through the same metadata contract
- **Extensibility**: New asset types and metadata fields can be added without breaking existing code
- **Queryability**: Files can be discovered and filtered by metadata without path conventions
- **Companion linking**: Related files (e.g. index + primary) are linked by CID references

## Architecture

```
Asset subclasses   (schema — typed Python fields via keyvalues)
      ↕  __getattr__ / __setattr__ coercion
  Asset.keyvalues  (transport — flat dict[str, str])
      ↕  upload() / query()
  StorageClient    (persistence — local TinyDB or Pinata)
```

There is no separate "storage primitive" layer. `Asset` is both the typed schema and the storage identity.

## Asset: The Base Class

`Asset` (`types/asset.py`) is a single dataclass for all typed file assets. Every file in the system is an Asset instance.

| Field | Type | Purpose |
|-------|------|---------|
| `cid` | `str` | Content identifier (IPFS or local hash) |
| `path` | `Path \| None` | Local filesystem path (set after download/upload) |
| `keyvalues` | `dict[str, str]` | Flat metadata for querying and routing |

### Subclass Declaration

Subclasses declare three class variables to define their schema:

- `_asset_key: ClassVar[str]` — the value for `keyvalues["asset"]` (e.g. `"reference"`, `"alignment"`)
- `_field_types: ClassVar[dict]` — field name to type (`bool`, `int`, `list`) for coercion
- `_field_defaults: ClassVar[dict]` — field name to default value

Subclasses auto-register in `Asset._registry` via `__init_subclass__`. The registry maps `_asset_key` strings to their class.

### Keyvalue Coercion

`__getattr__` and `__setattr__` transparently read/write `keyvalues` with type coercion:

- `bool`: stored as `"true"` / `"false"`, returned as Python `bool`
- `int`: stored as string, returned as Python `int`
- `list`: stored as comma-separated string, returned as Python `list[str]`
- `str`: no coercion needed

Accessing a missing key returns the default from `_field_defaults`, or `False` for bools, or `None`.

### Core Methods

- `fetch()` — downloads self, then queries for companions via `{_asset_key}_cid = self.cid` and downloads those too
- `update(path, **kwargs)` — sets keyvalues from kwargs, sets path, uploads to storage
- `to_dict()` / `from_dict()` — JSON serialization

## Asset Subclass Catalog

### Reference Assets (`types/reference.py`)

| Asset Key | Class | Fields | Notes |
|-----------|-------|--------|-------|
| `reference` | `Reference` | `build` | Has `contigs` property (reads .fai) |
| `reference_index` | `ReferenceIndex` | `build` | Companion via `reference_cid` |
| `sequence_dict` | `SequenceDict` | `build` | Companion via `reference_cid` |
| `aligner_index` | `AlignerIndex` | `build`, `aligner` | One asset per index file |

### Read Assets (`types/reads.py`)

| Asset Key | Class | Fields | Notes |
|-----------|-------|--------|-------|
| `r1` | `R1` | `sample_id` | Paired via `mate_cid` |
| `r2` | `R2` | `sample_id` | Paired via `mate_cid` |

### Alignment Assets (`types/alignment.py`)

| Asset Key | Class | Fields (coerced) | Notes |
|-----------|-------|------------------|-------|
| `alignment` | `Alignment` | `sample_id`, `duplicates_marked` (bool), `bqsr_applied` (bool) | Provenance via `reference_cid`, `r1_cid` |
| `alignment_index` | `AlignmentIndex` | `sample_id` | Companion via `alignment_cid` |
| `bqsr_report` | `BQSRReport` | `sample_id` | Linked via `alignment_cid` |
| `duplicate_metrics` | `DuplicateMetrics` | `sample_id` | Linked via `alignment_cid` |

### Variant Assets (`types/variants.py`)

| Asset Key | Class | Fields (coerced) | Notes |
|-----------|-------|------------------|-------|
| `variants` | `Variants` | `sample_id`, `caller`, `variant_type`, `build`, `sample_count` (int), `source_samples` (list) | |
| `variants_index` | `VariantsIndex` | `sample_id` | Companion via `variants_cid` |
| `known_sites` | `KnownSites` | `build` | Reference-scoped, used for BQSR |
| `vqsr_model` | `VQSRModel` | `sample_id`, `mode` | Produced by VariantRecalibrator |

## Companion Pattern

Assets link to related files via `{asset_key}_cid` keyvalues. When `fetch()` is called on an asset:

1. Downloads the asset itself
2. Queries for assets where `{_asset_key}_cid` equals this asset's CID
3. Downloads all matching companions

Example: `Reference(cid="Qmref").fetch()` also finds and downloads any `ReferenceIndex` with `reference_cid="Qmref"`.

## Assembly

`assemble(**filters)` is a module-level async function in `types/asset.py`. It queries storage with keyvalue filters, deduplicates by CID, and returns a flat `list[Asset]` of specialized subclass instances.

The `asset` filter key accepts a string or list of strings. List-valued filters produce cartesian product queries via `utils/query.py`.

Workflows filter results with `isinstance`:

```python
assets = await assemble(build="GRCh38", asset="reference")
ref = next(a for a in assets if isinstance(a, Reference))
```

## Specialization

`specialize(asset)` in `types/__init__.py` converts a base `Asset` to its registered subclass by looking up `keyvalues["asset"]` in `Asset._registry`. Returns the original instance if no match.

## Storage Layer

`utils/storage.py` defines the `StorageClient` protocol with four methods: `upload()`, `download()`, `query()`, `delete()`. The module-level `default_client` is resolved at import time based on environment:

- `STARGAZER_MODE=local` (default): `LocalStorageClient` (TinyDB), or `PinataClient` if `PINATA_JWT` is set
- `STARGAZER_MODE=cloud`: `PinataClient` (requires `PINATA_JWT`)

Tasks never call storage directly. All storage interaction flows through `Asset.fetch()` and `Asset.update()`.

## Task Pattern

Tasks receive typed Asset inputs, fetch them, run tools, then update outputs:

```python
@gatk_env.task
async def my_task(ref: Reference, aln: Alignment) -> Variants:
    await asyncio.gather(ref.fetch(), aln.fetch())
    # ... run tool using ref.path, aln.path ...
    vcf = Variants()
    await vcf.update(output_path, sample_id="NA12878")
    return vcf
```

## Workflow Pattern

Workflows accept scalar parameters and handle their own assembly. They call `assemble()` to query assets, filter by type, then pass typed assets to tasks:

```python
@gatk_env.task
async def my_workflow(build: str, sample_id: str) -> Variants:
    assets = await assemble(build=build, asset="reference")
    ref = next(a for a in assets if isinstance(a, Reference))
    # ... call tasks with ref, other typed assets ...
```

## MCP Server Integration

The server (`server.py`) exposes two execution tools:

- **`run_task`** — ad-hoc experimentation. Accepts `filters` dict, calls `assemble(**filters)` once, distributes assets to task parameters by matching `_asset_key` to type hints. Scalars passed via `inputs`.
- **`run_workflow`** — reproducible pipelines. Passes scalar `inputs` straight through; workflows handle their own assembly internally.

Storage tools (`query_files`, `upload_file`, `download_file`, `delete_file`) provide direct access to the storage layer for inspection and manual uploads.
