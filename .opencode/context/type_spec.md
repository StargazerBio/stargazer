# Stargazer IPFS Storage Spec

## Overview

Stargazer uses Pinata as a content-addressable storage layer where **keyvalue metadata is the query language**. Every file is self-describing, independently addressable, and queryable. Types emerge from metadata queries, not predefined hierarchies.

## Core Principle

**Keyvalue Absolutism**: Files share attributes rather than belonging to structures. A "Reference Genome" is not a directory—it's a query result.

## Metadata Schema

Every pinned file includes:

| Key | Required | Description |
|-----|----------|-------------|
| `type` | Yes | Maps 1:1 with a Stargazer dataclass (e.g., `Reference`, `Reads`, `Variants`) |
| `build` | No | Reference build (e.g., `GRCh38`, `GRCh37`) |
| `tool` | No | Tool that produced/requires this file (`fasta`, `faidx`, `bwa`, `minimap2`) |
| `sample_id` | No | Sample identifier for sample-specific data |
| `version` | No | Version string for reproducibility |

The `type` key is the only required attribute. All others are optional and used for filtering during hydration.

### Reference Example

A complete GRCh38 reference with indices:

```
CID: Qm...abc  | type: reference | build: GRCh38 | tool: fasta
CID: Qm...def  | type: reference | build: GRCh38 | tool: faidx
CID: Qm...ghi  | type: reference | build: GRCh38 | tool: bwa
```

## Hydration Pattern

Types hydrate by querying Pinata with inclusion filtering. The `type` attribute is fixed by the dataclass; all other attributes are passed as filters.

```python
Reference.hydrate(
    build="GRCh38",
    tool=["fasta", "faidx", "bwa"]
)
```

Internally:
1. Build query combinations from provided attributes
2. Query Pinata for each combination
3. Download matching CIDs to local paths
4. Assemble into FlyteDirectory or structured object

## Multi-Dimensional Queries

When any attribute is provided as a list, hydration produces the **cartesian product** of all list-valued attributes and fetches files matching each combination.

```python
Reference.hydrate(
    build="GRCh38",
    tool=["fasta", "faidx", "bwa"]
)
```

Produces queries:
1. `type=Reference AND build=GRCh38 AND tool=fasta`
2. `type=Reference AND build=GRCh38 AND tool=faidx`
3. `type=Reference AND build=GRCh38 AND tool=bwa`

A more complex example:

```python
Reference.hydrate(
    build=["GRCh38", "GRCh37"],
    tool=["fasta", "faidx"]
)
```

Produces 4 queries (2 builds × 2 tools):
1. `type=Reference AND build=GRCh38 AND tool=fasta`
2. `type=Reference AND build=GRCh38 AND tool=faidx`
3. `type=Reference AND build=GRCh37 AND tool=fasta`
4. `type=Reference AND build=GRCh37 AND tool=faidx`

The hydration method iterates through all produced metadata combinations and fetches any files that match each query.

## Multi-File Indices

Composite indices (e.g., BWA's `.amb`, `.ann`, `.bwt`, `.pac`, `.sa`) are pinned as a **single directory CID** with the appropriate `tool` tag.

## Error Handling

If a query returns zero results, **fail fast** with a clear error message indicating the missing component and metadata filter used.

## Schema Discipline

Canonical values must be enforced before pinning:
- Use `GRCh38` not `hg38` or `grch38`
- Use lowercase tool names
- Validate required keys per type

## Architectural Boundary

**Flyte never talks to IPFS directly.** Python code handles all Pinata API interactions and provides local file paths to Flyte tasks.