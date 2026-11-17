# Using the MCP Server

The MCP server gives any MCP client Stargazer's storage, its bundles and every task and workflow.

## Connecting a Client

Any MCP host that supports stdio or streamable HTTP transport works (see [CLI Interface](../architecture/cli.md) for the supported-client matrix). The server needs the `mcp` extra:

```bash
pip install "stargazer-bio[mcp]"
```

From a checkout, `uv pip install -e ".[mcp]"` does the same with your source.

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

The repository's own `.mcp.json` runs `pixi run stargazer` instead, in the development environment ([Contributing → Setup](contributing.md#setup)).

For remote access, run `stargazer --http` and connect over streamable HTTP (port 8000).

## Running a Task (Ad-hoc)

Use `run_task` for experimentation. Every parameter goes in `inputs` by name: an asset parameter takes the CID of a stored file of its type, a list of assets takes a list of CIDs, and the rest take plain values. Find the CIDs with `query_files`:

```
query_files(keyvalues={"asset": "reference", "build": "GRCh38_TP53"})
query_files(keyvalues={"sample_id": "NA12829", "asset": ["r1", "r2"]})

run_task(
    task_name="bwa_mem2_mem",
    inputs={"ref": "bafkrei…", "r1": "bafkrei…", "r2": "bafkrei…"}
)
```

`list_tasks(category="task")` lists each task's parameters and their types. Optional parameters can be left out. A CID that isn't in your storage, or is a file of another type than its parameter takes, is refused with the parameter's name. A public file is stored first with `fetch_resource_bundle` or `upload_file`.

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
| `publish_file(cid="bafkrei…")` | Make one of your stored files public with its companions (a reference's indices, say), under the same CIDs; your own copies stay |
| `list_bundles()` / `fetch_resource_bundle(bundle_name="variant_calling_demo")` | Fetch a curated set of public files, such as the TP53 reference and reads used above |

## Inspecting Resources

MCP resources provide read-only context:

- `stargazer://config` — whether a Pinata key is set, the store root, the index, the local directory, and how many tasks and workflows are registered
