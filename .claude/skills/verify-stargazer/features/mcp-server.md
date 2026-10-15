# MCP server tools

An agent harness connected to the `stargazer` MCP server over stdio lists the tasks and workflows `stargazer.tasks` and `stargazer.workflows` export, and runs one task by name with its asset inputs found by keyvalue filters. A task's output is stored as an asset and returned with its CID, path and keyvalues.

## Sub-features

- `mcp-list-tasks` lists every exported task (`list_tasks`, `category: "task"`) with its parameters.
- `mcp-run-task` runs one task by name (`run_task`), with `assemble()` filling its asset parameters from `filters`.

## How to get to it (user POV)

- Point an agent harness at the server (`uv run stargazer`, stdio), as in `docs/guides/mcp-server.md`, and ask it to list the tasks or run one.

## Driving it

`scripts/mcp_call.py` starts the server as a stdio subprocess, the way a harness does, and calls one tool.

Preconditions:

- The Launch block has run and the store is seeded with `scripts/seed_scrna.py`.
- No `.flyte/config.yaml` in the directory the server starts from. Without one, `run_task` runs the task in-process. With one, it submits to that cluster, which has to be reachable.

Steps:

- **List the tasks.** Run `uv run python .claude/skills/verify-stargazer/scripts/mcp_call.py list_tasks '{"category": "task"}' > "$RUN_DIR/evidence/mcp-list-tasks.txt"`. Exit code `0`, and every task in `stargazer.tasks.__all__` appears as a `"name"`.
- **Run a task.** Run `uv run python .claude/skills/verify-stargazer/scripts/mcp_call.py run_task '{"task_name": "qc_filter", "filters": {"asset": "anndata", "sample_id": "s1d1", "stage": "raw"}}' > "$RUN_DIR/evidence/mcp-run-task.txt"`. Exit code `0`, and the result is an `anndata` asset with `stage` `qc_filtered` and a `path` under `$STARGAZER_STORE_ROOT`.
- **Check the output.** Open the returned `path` with `anndata.read_h5ad(path, backed="r")`. Its `n_obs` and `n_vars` equal the returned keyvalues (6307 and 21675 for `s1d1`, measured 2026-10-14).
- **Proof.** Keep both outputs and the check.

## Gotchas

- The client sees only `Error executing tool <name>` when a tool raises. The cause is in the server's stderr, which `mcp_call.py` passes through, so redirect `2>` to a file to keep it.
- `list_tasks` prints one JSON object per entry, not one JSON array.
- To reproduce a bug on another checkout, run the script with `uv run --directory <checkout> python <path to mcp_call.py>`, which starts that checkout's server.
