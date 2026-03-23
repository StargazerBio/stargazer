# MCP Server

Stargazer exposes its bioinformatics capabilities through a [Model Context Protocol](https://modelcontextprotocol.io/) server, consumed by Claude Code or OpenCode.

## Transport Modes

| Transport | Client | Use Case |
|-----------|--------|----------|
| **stdio** (default) | Claude Code, OpenCode | Local. Client spawns `stargazer serve` as a subprocess. |
| **Streamable HTTP** | Remote MCP clients | Remote. `stargazer serve --http`. |

The same server implementation supports both transports, selected at startup via CLI flag.

## Tools

### Discovery

| Tool | Description | Inputs |
|------|-------------|--------|
| `list_tasks` | List available tasks and workflows with signatures | `category: str \| None` (filter by `"task"` or `"workflow"`) |

Returns a catalog of registered tasks with name, category, description, parameters, and output types.

### Execution

| Tool | Description | Inputs |
|------|-------------|--------|
| `run_task` | Execute a single task (ad-hoc) | `task_name: str, filters: dict, inputs: dict \| None` |
| `run_workflow` | Execute a named workflow (reproducible) | `workflow_name: str, inputs: dict` |

**`run_task`** is for experimentation — it accepts `filters`, calls `assemble(**filters)` to gather assets, and distributes them to task parameters by matching `_asset_key` to type hints. Scalars and paths are passed via `inputs`.

**`run_workflow`** is for production — it passes scalar `inputs` straight through. Workflows handle their own assembly internally.

Tasks and workflows are not registered as individual MCP tools. The client discovers what's available via `list_tasks`, then invokes them through `run_task` or `run_workflow`.

### Storage

| Tool | Description | Inputs |
|------|-------------|--------|
| `query_files` | Find files by metadata | `keyvalues: dict[str, str]` |
| `upload_file` | Upload a file with metadata | `path: str, keyvalues: dict[str, str]` |
| `download_file` | Download a file by CID to local cache | `cid: str` |
| `delete_file` | Delete a file by CID | `cid: str` |

`upload_file` validates that `keyvalues["asset"]` is a registered asset key and that all other keys are declared fields on that asset subclass.

### Bundles

| Tool | Description | Inputs |
|------|-------------|--------|
| `list_bundles` | List available resource bundles | (none) |
| `fetch_resource_bundle` | Download a predefined bundle into local storage | `bundle_name: str` |

Bundles are curated sets of files defined as YAML manifests in the codebase. Each file carries a `bundle` keyvalue for queryability. `fetch_resource_bundle` downloads bytes by CID via the standard path. In local mode (no JWT), it also seeds TinyDB with the manifest's keyvalues so `assemble()` can discover them. In remote mode (JWT set), metadata already exists in Pinata. See [Configuration — Resource Bundles](configuration.md#resource-bundles).

## Resources

| Resource | URI | Description |
|----------|-----|-------------|
| Server configuration | `stargazer://config` | Current mode, local directory, task/workflow counts |

## Type Serialization

MCP tools accept and return JSON. Asset dataclasses serialize via `to_dict()`. Task outputs are marshalled through `marshal_output` — single outputs are returned directly, multi-output tasks return `{"o0": ..., "o1": ...}`.

## Error Handling

Tool errors return structured content with error type and actionable message. The server does not crash on tool failure — it reports the error through the MCP response.
