# Using the MCP Server

This guide covers interacting with Stargazer through the MCP server.

## Running a Task (Ad-hoc)

Use `run_task` for experimentation. Provide filters to select assets and inputs for scalar parameters:

```
run_task(
    task="align_with_bwa",
    filters={"build": "GRCh38", "sample_id": "NA12878", "asset": ["reference", "r1", "r2"]},
    inputs={}
)
```

The server calls `assemble(**filters)`, matches assets to task parameters by `_asset_key`, and executes the task.

## Running a Workflow (Reproducible)

Use `run_workflow` for production pipelines. Pass only scalar inputs — the workflow handles its own assembly:

```
run_workflow(
    workflow="germline_single_sample",
    inputs={"build": "GRCh38", "sample_id": "NA12878"}
)
```

## Managing Files

| Tool | Use |
|------|-----|
| `query_files(keyvalues={"asset": "reference", "build": "GRCh38"})` | Find files by metadata |
| `upload_file(path="/data/ref.fa", keyvalues={"asset": "reference", "build": "GRCh38"})` | Upload with metadata |
| `download_file(file_id="abc123")` | Download to local cache |
| `delete_file(file_id="abc123")` | Remove a file |

## Inspecting Resources

MCP resources provide read-only context:

- `stargazer://references` — available reference builds
- `stargazer://samples` — available samples
- `stargazer://workflows` — workflow catalog
- `stargazer://config` — current mode and storage backend
