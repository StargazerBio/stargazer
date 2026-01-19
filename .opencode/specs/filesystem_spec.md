# Filesystem & Type System Specification

## Design Goals

This design brings rigour and interoperability between bioinformatics tools by establishing a consistent interface for file metadata. Every file carries structured keyvalue metadata that describes its role, enabling:

- **Consistency**: All tools produce and consume files through the same metadata contract
- **Extensibility**: New types, components, and metadata fields can be added without breaking existing code
- **Queryability**: Files can be discovered and filtered by metadata without path conventions

## IpFile: The Metadata-Enriched File

`IpFile` is the foundational abstraction. Every file in Stargazer carries structured `keyvalues` metadata:

| Field | Purpose |
|-------|---------|
| `type` | The logical type this file belongs to (`reference`, `reads`, `alignment`, `variants`) |
| `component` | The role this file plays within its type (`fasta`, `faidx`, `r1`, `alignment`, `vcf`, etc.) |
| `sample_id` | Sample identifier (for sample-scoped types) |
| `build` | Reference genome build (for reference-scoped types) |
| Additional fields | Domain-specific metadata (`caller`, `sorted`, `duplicates_marked`, etc.) |

This metadata is set at upload time and becomes immutable for that file version.

## Higher-Level Types

Types (`Reference`, `Reads`, `Alignment`, `Variants`) are component containers. Each holds one or more `IpFile` references organized by component role:

- **Reference**: `fasta`, `faidx`, `aligner_index` (list)
- **Reads**: `r1`, `r2`
- **Alignment**: `alignment`, `index`
- **Variants**: `vcf`, `index`

Types expose properties that read from component keyvalues (e.g., `alignment.is_sorted` reads from the alignment file's `sorted` keyvalue). This creates a uniform interface where metadata lives on files but is accessible through typed properties.

## Component Metadata Contract

The `component` keyvalue field is the critical bridge between files and types. It specifies the semantic role of a file:

| Type | Component | Description |
|------|-----------|-------------|
| reference | fasta | Reference FASTA sequence |
| reference | faidx | FASTA index (.fai) |
| reference | aligner_index | Aligner-specific index files |
| reads | r1 | Forward reads (R1) |
| reads | r2 | Reverse reads (R2) |
| alignment | alignment | BAM/CRAM file |
| alignment | index | BAM/CRAM index (.bai/.crai) |
| variants | vcf | VCF/GVCF file |
| variants | index | VCF index (.tbi) |

## Update Methods

Each type provides named `update_{component}()` methods that:

1. Accept a local `Path` and explicit metadata arguments
2. Construct keyvalues from arguments (no arbitrary dicts)
3. Upload to IPFS (or caches locally) via `PinataClient`
4. Assign the resulting `IpFile` to the component field
5. Return the `IpFile`

This enforces metadata correctness at the method signature level rather than runtime validation.

## Hydration

The `hydrate()` task reverses the flow: given keyvalue filters, it queries IPFS and reconstructs type instances by routing files to component fields based on their `type` and `component` keyvalues.

## Task Interoperability

This design enables a consistent pattern for tool tasks:

1. **Input**: Receive typed objects (`Alignment`, `Reference`, etc.)
2. **Fetch**: Download component files to local cache via `fetch()`
3. **Execute**: Run tool using `ipfile.local_path` for file paths
4. **Output**: Call `update_{component}()` on output files
5. **Return**: Return updated type instance

Every tool task follows this contract, making pipelines composable and metadata automatically propagated.
