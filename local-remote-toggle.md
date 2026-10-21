---
title: In-notebook local-vs-remote toggle UI
status: done
priority: normal
created: 2026-05-19
pr: 62
---

Formalize the dispatch choice as a reusable `mo.ui` element (radio / segmented control) so individual cells don't need to hardcode `flyte.with_runcontext(mode="local").run` vs `flyte.run`.

## Design

One module, `stargazer.notebooks.ui`, with two functions. It's its own module rather than the package `__init__` because it imports marimo, and the dashboard imports `stargazer.notebooks` without the notebook extra.

- `run_location() -> mo.ui.radio`: an inline radio labelled "Run" with two options, "On this machine" (the default) and "On the cluster". Its value is the Flyte run mode, `"local"` or `"remote"`.
- `async dispatch(location, task, **inputs)`: runs `task` with `flyte.with_runcontext(mode=location.value).run`, waits for it, and returns its output, the same value awaiting the task gives. One output only, which is every caller's case today.

A notebook drops the control in one cell and dispatches in another (marimo refuses to read an element's value in the cell that made it), and changing the control re-runs the dispatching cell.

```python
where = run_location()
where
```

```python
summaries = await dispatch(where, audit_cohorts, sheets=sheets)
```

"On the cluster" forces remote mode rather than calling `flyte.run`, which runs in-process when no cluster is configured (measured: `flyte.run` with no endpoint returned an `_InlineRun`), so the control never claims a cluster run that happened locally.

## Where it's used

- [x] The Execution tutorial keeps its two explicit calls, and a closing section introduces the control as the reusable form, running `audit_cohorts` wherever it's set.

The scRNA notebook and the `basic` template don't get it here. Neither dispatches: they await their workflows in-process. And their workflows are defined in regular cells, which a cluster can't load: Flyte's task pod imports the notebook module and looks the task up as an attribute, and importing a marimo notebook doesn't run its cells. Measured with a throwaway notebook: a cell-defined task's loader args resolved to `AttributeError: module 'cell_task' has no attribute 'cell_task'`, and the same task as `@app.function` loaded. Ticket `notebook-cluster-runs` covers that.

## Pieces

- [x] Unit tests: `dispatch` runs local when the control is on this machine and remote when it's on the cluster, and returns the task's output
- [x] `stargazer.notebooks.ui`
- [x] Execution tutorial section
- [x] Docs: `docs/architecture/notebook.md`, API reference (no guide shows the hardcoded dispatch)
- [x] Verified headless with the control on this machine against an isolated store

## Outcome

Shipped in PR #62 (merge `40c329e`): `stargazer.notebooks.ui` with `run_location()` and `dispatch()`, a closing "Let the Reader Pick" section in the Execution tutorial, and the control described in `docs/architecture/notebook.md`.

Verified: unit tests written first (failed on `NotImplementedError`), with a mutation check on the cluster path's `wait()`; unit tier 504 passed. The Execution tutorial driven headless against an isolated store: the control rendered with "On this machine" as its default, and section 6 returned 3 `CohortSummary` results with the same CIDs as section 3. "On the cluster" with no cluster configured raised at upload rather than running locally.

Left: a real cluster run through the control was not verified (only a patched-runner unit test covers it). The scRNA notebook and the `basic` template move onto the control in ticket `notebook-cluster-runs`. `dispatch` handles one output only and shows no console link for a cluster run.
