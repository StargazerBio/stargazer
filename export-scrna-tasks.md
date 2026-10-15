---
title: Export the scRNA tasks from stargazer.tasks
status: review
priority: high
created: 2026-10-09
pr: 30
---

The scRNA tasks aren't exported from `stargazer.tasks`, so `list_tasks`
and the catalog omit them, and `run_task` can't run them.

Found in the docs correctness sweep (2026-10-09, #18).

## Verification

Branch `fix/export-scrna-tasks`. Measured 2026-10-14 against an isolated
store seeded with `scrna_demo`, through the MCP server over stdio
(verify-stargazer's new `mcp-server` feature, `scripts/mcp_call.py`):

- `main`: `run_task` for `qc_filter` raises `ValueError: Unknown task`.
- Branch: `list_tasks` lists all six scRNA tasks, and `run_task` runs
  `qc_filter` for `s1d1` and stores `s1d1_qc_filtered.h5ad`, whose 6307 x 21675
  matches its keyvalues.
- `test_discovery_finds_all_tasks` failed before the fix on exactly the six
  names; the unit tier passes (429).
- `docs/reference/catalog.md` gains the six rows, matching the pre-commit
  catalog generator.
