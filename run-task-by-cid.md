---
title: run-task-by-cid
status: doing
priority: low
created: 2026-11-16
---

The MCP server's `run_task` fills a task's asset parameters from one `assemble(**filters)` call, and every filter must match every asset. Its own docstring says what follows: assets with different keys, a reference's `build` and a sample's `sample_id`, can't be filled from one call. So it can't run `bwa_mem`, `haplotype_caller`, `base_recalibrator` or any other task that takes a reference and a sample's file (read from `server.py`, 2026-11-16; not driven).

Take each asset parameter by CID instead, in `inputs` beside the scalars:

```json
{"task_name": "bwa_mem2_mem", "inputs": {"ref": "bafk…", "r1": "bafk…", "r2": "bafk…"}}
```

An agent finds the CIDs with `query_files`, which it already has.

## Plan

- [ ] `run_task(task_name, inputs)`: a parameter whose hint is an asset type takes a CID, looked up in the index and specialized; a `list[Asset]` takes a list of CIDs. A CID that isn't found, or is the wrong type, is refused by name. `filters` and `_asset_key_for_hint`'s matching go.
- [ ] `docs/architecture/mcp-server.md`, `docs/guides/mcp-server.md`, `runtime/notebook_agent.md`.

Moot if the server goes (ticket [[skills-replace-mcp]]).

Related: [[board]], [[skills-replace-mcp]], [[agent-mcp]].
