# MCP Server

Stargazer exposes its bioinformatics capabilities through a [Model Context Protocol](https://modelcontextprotocol.io/) server, consumed by Claude Code or OpenCode.

## Transport Modes

| Transport | Client | Use Case |
|-----------|--------|----------|
| **stdio** (default) | Claude Code, OpenCode | Local. The client spawns `stargazer` as a subprocess. |
| **Streamable HTTP** | Remote MCP clients, the notebook's agent panel | Remote. `stargazer --http`. |

The same server implementation supports both transports, selected at startup by the `--http` flag. The `stargazer` command needs the `mcp` extra installed.

A notebook pod in edit mode runs the server over HTTP on loopback, and the agents in marimo's agent panel get it in every session ([Notebook Runtime → The Proxy](runtime.md#the-proxy)). Its runs go to the pod's backend, in a hosted pod the owner's own project.

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
| `download_file` | Download a file by CID to the local cache | `cid: str` |
| `delete_file` | Delete a file's index row and stored bytes by CID | `cid: str` |
| `update_file` | Merge a metadata patch onto an existing file | `cid: str, keyvalues: dict[str, str]` |
| `publish_file` | Upload one of the user's stored files to the public tier, same CID | `cid: str` |

`upload_file` and `update_file` validate through `build_asset()` ([Types](types.md)): `keyvalues["asset"]` is required, underscore-prefixed keys are reserved, and a registered kind must parse to its declared fields (other keys become [extras](types.md)). `update_file` merges its patch onto the existing row (keys added or overwritten, none removed, CID untouched) so mis-tagged records can be fixed in place. `download_file` falls back to the public gateway for a CID not in the user's index. `publish_file` needs a Pinata key ([Configuration → The public tier](configuration.md#the-public-tier)).

### Bundles

| Tool | Description | Inputs |
|------|-------------|--------|
| `list_bundles` | List available resource bundles | (none) |
| `fetch_resource_bundle` | Download a predefined bundle into local storage | `bundle_name: str` |

`fetch_resource_bundle` registers a bundle's public files in the user's index ([Configuration → Resource Bundles](configuration.md#resource-bundles)).

## Resources

| Resource | URI | Description |
|----------|-----|-------------|
| Server configuration | `stargazer://config` | Whether a Pinata key is set, the store root, the index, the local directory, and task/workflow counts |

## Type Serialization

MCP tools accept and return JSON. Asset dataclasses serialize via `to_dict()`. Task outputs are marshalled through `marshal_output` — single outputs are returned directly, multi-output tasks return `{"o0": ..., "o1": ...}`.

## Error Handling

A tool that raises returns an MCP error result carrying the exception's message: an unknown task or workflow names the available ones, and a task whose asset parameter matched nothing names the filters it tried. The server keeps running.
