---
title: export-scrna-tasks
status: done
priority: high
created: 2026-10-09
pr: 30
---

The scRNA tasks aren't exported from `stargazer.tasks`, so `list_tasks`
and the catalog omit them, and `run_task` can't run them.

Found in the docs correctness sweep (2026-10-09, #18).

## Verification

Branch `fix/export-scrna-tasks`.

- `test_discovery_finds_every_defined_task` walks every module under
  `stargazer.tasks` and requires the registry to hold each task defined there,
  replacing a hand-kept list that had the same omission. Against `main`'s
  exports it fails on exactly the six scRNA tasks; with the fix it passes. The
  unit tier passes (429).
- Measured 2026-10-14 through the MCP server over stdio, against an isolated
  store seeded with `scrna_demo`: on `main`, `run_task` for `qc_filter` raises
  `ValueError: Unknown task`. On the branch, `list_tasks` lists all six scRNA
  tasks, and `run_task` runs `qc_filter` for `s1d1` and stores
  `s1d1_qc_filtered.h5ad`, whose 6307 x 21675 matches its keyvalues. The MCP
  feature and stdio client written for that run were dropped in review in
  favour of the unit test.
- `docs/reference/catalog.md` gains the six rows, matching the pre-commit
  catalog generator.

## Outcome

Shipped in PR #30 (merged 2026-10-15). `stargazer.tasks` exports the six
scRNA tasks, so `list_tasks`, the catalog and `run_task` all see them. A unit
test now walks every module under `stargazer.tasks` and requires the registry
to hold each task defined there, in place of the hand-kept list that had the
same gap.

Verified with that test (it fails against `main`'s exports on exactly the six
scRNA tasks), the unit tier, and through the MCP server over stdio: `run_task`
ran `qc_filter` for `s1d1` and stored a 6307 x 21675 file matching its
keyvalues.

Left: nothing.

Related: [[workflow-export-check]].
