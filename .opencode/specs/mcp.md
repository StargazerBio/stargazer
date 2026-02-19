# MCP Server Specification

## Design Goals

Stargazer exposes its bioinformatics capabilities through a Model Context Protocol (MCP) server. This provides a standardized interface that any MCP-compatible client can consume — Claude Code, OpenCode, Claude Desktop, or any other MCP host.

The MCP server is the primary interface for CLI users who bring their own MCP-compatible client. The browser frontend (Chainlit) calls tasks directly via Python imports and does not use the MCP wire protocol internally.

## Transport Modes

| Transport | Client | Use Case |
|-----------|--------|----------|
| **stdio** | Claude Code, OpenCode, Claude Desktop | Local mode. Client spawns `stargazer serve` as a subprocess. |
| **Streamable HTTP** | Remote MCP clients, MCP Inspector | Remote mode. Client connects to a hosted MCP server over HTTP/SSE. |

The same MCP server implementation supports both transports. The transport is selected at startup, not compiled in. The browser frontend (Chainlit) does not use either transport — it calls tasks directly.

## Server Capabilities

The Stargazer MCP server exposes three primitive types:

### Tools

Tools are actions the LLM can invoke. They map directly to Stargazer's existing task and storage functions.

#### Storage Tools

| Tool | Description | Inputs | Output |
|------|-------------|--------|--------|
| `query_files` | Find files by metadata | `keyvalues: dict[str, str]` | List of file metadata (id, name, size, keyvalues) |
| `upload_file` | Upload a file with metadata | `path: str, keyvalues: dict[str, str]` | File metadata |
| `download_file` | Download a file to local cache | `file_id: str` | Local path |
| `delete_file` | Delete a file | `file_id: str` | Success/failure |

#### Workflow Tools

| Tool | Description | Inputs | Output |
|------|-------------|--------|--------|
| `run_workflow` | Execute a named workflow | `workflow: str, params: dict` | Run ID + status |
| `get_run_status` | Check workflow run status | `run_id: str` | Status, progress, errors |
| `get_run_logs` | Stream logs from a run | `run_id: str` | Log content |

#### Individual Task Tools

Each Flyte task is registered as an MCP tool. The tool name matches the Python function name. Parameters and descriptions are derived from the function signature and docstring.

| Tool | Description |
|------|-------------|
| `hydrate` | Query and reconstruct typed objects from file metadata |
| `bwa_index` | Create BWA index for a reference genome |
| `bwa_mem` | Align reads to a reference using BWA-MEM |
| `samtools_faidx` | Create FASTA index |
| `sort_sam` | Sort alignment by coordinate or queryname |
| `mark_duplicates` | Mark duplicate reads |
| `base_recalibrator` | Generate BQSR recalibration table |
| `apply_bqsr` | Apply base quality score recalibration |
| `create_sequence_dictionary` | Create sequence dictionary for reference |
| `genotype_gvcf` | Genotype a GVCF |
| `combine_gvcfs` | Combine multiple GVCFs |
| `genomics_db_import` | Import GVCFs into GenomicsDB |
| `variant_recalibrator` | Build variant quality recalibration model |
| `apply_vqsr` | Apply variant quality score recalibration |

#### Composite Workflow Tools

| Tool | Description |
|------|-------------|
| `prepare_reference` | Prepare reference with all indices |
| `preprocess_sample` | Full preprocessing pipeline for one sample |
| `preprocess_cohort` | Preprocess multiple samples in parallel |
| `germline_single_sample` | End-to-end germline variant calling for one sample |
| `germline_cohort` | Joint genotyping across a cohort |
| `germline_cohort_with_vqsr` | Cohort calling with variant quality recalibration |

### Resources

Resources are read-only data the LLM can inspect for context.

| Resource | URI Pattern | Description |
|----------|-------------|-------------|
| Available reference genomes | `stargazer://references` | List of reference builds with available components |
| Available samples | `stargazer://samples` | List of sample IDs with available data types |
| Workflow catalog | `stargazer://workflows` | List of available workflows with parameter descriptions |
| Run history | `stargazer://runs` | Recent workflow runs with status |
| Server configuration | `stargazer://config` | Current mode, storage backend, available tools |

### Prompts

Prompts are reusable templates for common bioinformatics workflows.

| Prompt | Description | Parameters |
|--------|-------------|------------|
| `align_reads` | Align reads to a reference genome | `sample_id`, `ref_build` |
| `preprocess_sample` | Full data preprocessing (align, sort, dedup, BQSR) | `sample_id`, `ref_build`, `known_sites` |
| `call_variants` | Germline variant calling pipeline | `sample_id`, `ref_build` |
| `joint_genotype` | Joint genotyping across a cohort | `sample_ids`, `ref_build`, `cohort_id` |

## Mode Awareness

The MCP server reads `STARGAZER_MODE` at startup and configures itself accordingly:

| Mode | Storage | Execution | Required |
|------|---------|-----------|----------|
| `local` (no JWT) | LocalStorageClient | Flyte local | Nothing |
| `local` (with JWT) | PinataClient | Flyte local | `PINATA_JWT` |
| `cloud` | PinataClient | Flyte remote (Union) | `PINATA_JWT`, Union config |

Tools that require remote infrastructure are not registered in local mode. The LLM sees only what's available.

## Type Serialization

MCP tools accept and return JSON. Stargazer's Python dataclasses are serialized as follows:

| Type | JSON Representation |
|------|-------------------|
| `IpFile` | `{id, cid, name, size, keyvalues, created_at, is_public}` |
| `Reference` | `{build, fasta: IpFile?, faidx: IpFile?, sequence_dictionary: IpFile?, aligner_index: [IpFile]}` |
| `Reads` | `{sample_id, r1: IpFile?, r2: IpFile?, read_group: dict?}` |
| `Alignment` | `{sample_id, alignment: IpFile?, index: IpFile?}` |
| `Variants` | `{sample_id, vcf: IpFile?, index: IpFile?}` |

## Notifications

The server emits notifications for:

- `notifications/tools/list_changed` — when new tasks are registered or mode changes
- Progress updates during long-running workflow executions (via MCP progress tokens)

## Error Handling

Tool errors return structured content with error type and actionable message. The server does not crash on tool failure — it reports the error through the MCP response and lets the LLM decide how to proceed.
