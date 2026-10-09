# Using the MCP Server

This guide covers interacting with Stargazer through the MCP server.

## Connecting a Client

Any MCP host that supports stdio or streamable HTTP transport works (see [CLI Interface](../architecture/cli.md) for the supported-client matrix). The server needs the `mcp` extra, so install the package with it from a checkout:

```bash
uv pip install -e ".[mcp]"
```

For stdio, point the client at the `stargazer` command:

```json
{
  "mcpServers": {
    "stargazer": {
      "command": "stargazer",
      "args": []
    }
  }
}
```

The repository's own `.mcp.json` runs `uv run stargazer` instead, which uses the project venv a contributor set up with `uv sync --all-extras`.

For remote access, run `stargazer --http` and connect over streamable HTTP (port 8000).

## Running a Task (Ad-hoc)

Use `run_task` for experimentation. Provide filters to select assets and inputs for scalar parameters:

```
run_task(
    task_name="samtools_faidx",
    filters={"asset": "reference", "build": "GRCh38_TP53"},
    inputs={}
)
```

The server calls `assemble(**filters)`, matches assets to task parameters by `_asset_key`, and executes the task. Every filter must match each asset it returns, so one filter set can only fill parameters whose assets share those keys: a reference (`build`) and a sample's reads (`sample_id`) never both match `{"build": ..., "sample_id": ...}`. Run a multi-asset pipeline through its workflow.

## Running a Workflow (Reproducible)

Use `run_workflow` for production pipelines. Pass only scalar inputs — the workflow handles its own assembly:

```
run_workflow(
    workflow_name="germline_short_variant_discovery",
    inputs={"build": "GRCh38_TP53", "sample_ids": ["NA12829"], "cohort_id": "tp53"}
)
```

`list_tasks(category="workflow")` lists every workflow with its parameters.

## Managing Files

| Tool | Use |
|------|-----|
| `query_files(keyvalues={"asset": "reference", "build": "GRCh38"})` | Find files by metadata |
| `upload_file(path="/data/ref.fa", keyvalues={"asset": "reference", "build": "GRCh38"})` | Upload with metadata |
| `download_file(cid="bafkrei…")` | Download to the local cache |
| `delete_file(cid="bafkrei…")` | Remove a file |
| `update_file(cid="bafkrei…", keyvalues={"asset": "reference", "build": "GRCh38"})` | Fix a mis-tagged record's metadata in place (merge, CID unchanged) |
| `list_bundles()` / `fetch_resource_bundle(bundle_name="variant_calling_demo")` | Fetch a curated set of public files, such as the TP53 reference and reads used above |

## Inspecting Resources

MCP resources provide read-only context:

- `stargazer://config` — whether a Pinata key is set, the store root, the index, the local directory, and how many tasks and workflows are registered
