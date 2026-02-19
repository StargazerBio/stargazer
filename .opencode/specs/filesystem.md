# Filesystem & Type System Specification

## Design Goals

This design brings rigour and interoperability between bioinformatics tools by establishing a consistent interface for file metadata. Every file carries structured keyvalue metadata that describes its role, enabling:

- **Consistency**: All tools produce and consume files through the same metadata contract
- **Extensibility**: New types, components, and metadata fields can be added without breaking existing code
- **Queryability**: Files can be discovered and filtered by metadata without path conventions

## Three-Layer Architecture

```
Typed File Components  (schema — what metadata exists, typed Python fields)
        ↕  to_keyvalues() / from_keyvalues()
    IpFile.keyvalues   (transport — flat dict[str, str])
        ↕  upload_file() / query_files()
  TinyDB / Pinata      (storage — persistence)
```

## IpFile: The Storage Primitive

`IpFile` is the storage-layer abstraction. It holds an IPFS content identifier, file metadata, and an untyped `keyvalues: dict[str, str]` bag. IpFile does not know what the keyvalues mean — it is a transport container. Meaning is defined by the typed file component layer above it.

| Field | Purpose |
|-------|---------|
| `id` | Unique identifier |
| `cid` | Content hash (IPFS or local) |
| `name` | Original filename |
| `size` | File size in bytes |
| `keyvalues` | Flat string metadata for querying |
| `created_at` | Creation timestamp |
| `local_path` | Cached local path (set after download) |
| `is_public` | Visibility flag |

IpFile is unchanged by this design. It remains a dumb storage primitive.

## FileComponent: The Schema Layer

`FileComponent` is the base dataclass for all typed file components. Each subclass declares:

- `TYPE: ClassVar[str]` — the logical type (e.g. `"alignment"`)
- `COMPONENT: ClassVar[str]` — the role within that type (e.g. `"alignment"`)
- Named metadata fields with proper Python types (str, bool, int, list[str], Literal)
- `ipfile: IpFile | None` — the storage identity, set after upload/download

The base class provides:
- `to_keyvalues()` — serializes typed fields to `dict[str, str]` for storage
- `from_keyvalues()` — deserializes from `dict[str, str]` back to typed fields
- `to_dict()` / `from_dict()` — JSON-friendly serialization for MCP transport

Field name = keyvalue key (1:1 mapping, no renaming). Type conversions are automatic: `bool` ↔ `"true"`/`"false"`, `int` ↔ `str`, `list[str]` ↔ comma-separated, `None` → omitted.

## File Component Definitions

### Reference Components (`types/reference.py`)

| Class | TYPE | COMPONENT | Metadata Fields |
|-------|------|-----------|----------------|
| `Fasta` | reference | fasta | `build` |
| `Faidx` | reference | faidx | `build`, `tool` |
| `SequenceDict` | reference | sequence_dictionary | `build`, `tool` |
| `AlignerIndex` | reference | aligner_index | `build`, `aligner` |

### Alignment Components (`types/alignment.py`)

| Class | TYPE | COMPONENT | Metadata Fields |
|-------|------|-----------|----------------|
| `AlignmentFile` | alignment | alignment | `sample_id`, `format`, `sorted`, `duplicates_marked`, `bqsr_applied`, `tool` |
| `AlignmentIndex` | alignment | index | `sample_id` |

### Reads Components (`types/reads.py`)

| Class | TYPE | COMPONENT | Metadata Fields |
|-------|------|-----------|----------------|
| `R1File` | reads | r1 | `sample_id`, `sequencing_platform` |
| `R2File` | reads | r2 | `sample_id`, `sequencing_platform` |

### Variants Components (`types/variants.py`)

| Class | TYPE | COMPONENT | Metadata Fields |
|-------|------|-----------|----------------|
| `VariantsFile` | variants | vcf | `sample_id`, `caller`, `variant_type`, `build`, `sample_count`, `source_samples` |
| `VariantsIndex` | variants | index | `sample_id` |

## Container Types

Container types (`Reference`, `Reads`, `Alignment`, `Variants`) are thin compositions that group related file components. They hold an identity field (`build` or `sample_id`) and optional typed file component fields.

- **Reference**: `build`, `fasta: Fasta`, `faidx: Faidx`, `sequence_dictionary: SequenceDict`, `aligner_index: list[AlignerIndex]`
- **Reads**: `sample_id`, `r1: R1File`, `r2: R2File`, `read_group: dict`
- **Alignment**: `sample_id`, `alignment: AlignmentFile`, `index: AlignmentIndex`
- **Variants**: `sample_id`, `vcf: VariantsFile`, `index: VariantsIndex`

Containers provide:
- `fetch()` — downloads all component `ipfile`s to local cache
- `to_dict()` / `from_dict()` — delegates to each component's serialization
- `is_paired` on Reads (derived from container state, not a single file)

Containers do **not** have `update_*()` methods or property proxies into component keyvalues. Metadata is accessed directly on the component: `alignment.alignment.duplicates_marked`, not `alignment.has_duplicates_marked`.

## Upload Pattern

File upload is handled by `upload_component()`, a standalone async helper:

1. Task constructs a typed file component with metadata fields set
2. Calls `upload_component(component, path)` which:
   a. Calls `component.to_keyvalues()` to get the flat metadata dict
   b. Calls `storage_client.upload_file(path, keyvalues=kv)` to store the file
   c. Attaches the resulting `IpFile` to `component.ipfile`
3. Task assigns the component to the container

This separates metadata construction (typed, validated at construction time) from storage (async side effect).

## Hydration

The `hydrate()` task reverses the flow: given keyvalue filters, it queries storage and reconstructs typed instances:

1. Query files from storage by keyvalue filters
2. For each IpFile, look up `(type, component)` to find the FileComponent subclass
3. Construct the component via `ComponentClass.from_keyvalues(kv, ipfile=ipfile)`
4. Group components by identity (`build` or `sample_id`)
5. Assemble container types from grouped components

## Task Interoperability

Tool tasks follow a consistent pattern:

1. **Input**: Receive container types (`Alignment`, `Reference`, etc.)
2. **Fetch**: Download component files to local cache via `container.fetch()`
3. **Execute**: Run tool using `component.ipfile.local_path` for file paths
4. **Output**: Construct typed file components with metadata, upload via `upload_component()`
5. **Return**: Assemble and return container with new components
