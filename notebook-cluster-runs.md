---
title: notebook-cluster-runs
status: done
priority: normal
created: 2026-10-20
pr: 85
---

The scRNA notebook and the `basic` template define their workflows in regular cells and await them in-process. A cluster can't run those: Flyte's task pod imports the notebook module and looks the task up as an attribute, and importing a marimo notebook runs its setup block and `@app.function` cells, not its regular cells. Measured 2026-10-20 with a throwaway notebook, resolving a task the way a pod does: defined in a cell, `AttributeError: module 'cell_task' has no attribute 'cell_task'`; the same task as `@app.function` over `@env.task`, loaded. The Execution tutorial already submits its remote run that way, importing `audit_cohorts` from the Workflows tutorial, where it's an `@app.function`.

The `basic` template's Run section also says `flyte.run(my_workflow, ...)` reaches a remote endpoint once one is configured, which the above says it wouldn't.

To do, per notebook: move the workflow (and the env, task and asset it needs) into the setup block and `@app.function` / `@app.class_definition` cells, check the env's image has what the task imports (the template's `my_env` has no image, so a pod gets Flyte's base image without stargazer), then swap the await for the `run_location()` control and `dispatch()` from ticket [[local-remote-toggle]]. Verify with one real cluster run each. The scRNA notebook's workflows also change with ticket [[qc-filter-organism-from-asset]], which goes first.

## Verification

Branch `feat/notebook-cluster-runs`, test account's dashboard deployed from cc202fe, 2026-10-26.

- scRNA notebook, hosted Run mode, set to **On the cluster**: `preprocess` (`u4xcsk997cqmjf6z7dzw`, `utwz668tgt6x8kp7sj6m`) and `cluster_and_annotate` (`ugl8r9x8vjcznvmvvpz6`, `uf4m78pxbzvc725cpl29`) succeeded; UMAPs and summary rendered: s1d1 6,307 cells, 16 clusters; s1d3 7,157 cells, 17 clusters. The cell counts match the local drive.
- A workspace notebook created from **Basic** (`/workspace/cluster-run-1026.py`), Edit mode, a CSV uploaded, set to **On the cluster**: run `udqmc2knpgxx695zr6r8`, `template.my_workflow` and its child `template.my_task` succeeded, output a `MyAsset` with the uploaded file's CID.
- Local drive of the scRNA notebook (verify-stargazer, **On this machine**): export exit 0, every stage `ok` for both samples.
- The first hosted drive found `run.outputs()` hands back schema-rebuilt look-alikes without `Asset` methods (`'AnnData' object has no attribute 'fetch'`); `dispatch` now decodes with `typed_outputs` into the task's declared types.
- **On this machine** in a hosted scRNA notebook fails on a missing `scikit-image`, which predates this change: ticket [[scrna-notebook-hosted-deps]].

## Outcome

Shipped in PR #85 (merge `9d10626`). The scRNA notebook's and the Basic template's workflows are `@app.function`s over setup-block envs, run through `dispatch()` with a `run_location()` control; `dispatch()` bundles from the dispatched task's own root and returns cluster outputs as the task's declared types. Verified by the unit tier (`test_cluster_runnable.py`, `test_ui.py`), a local drive of the scRNA notebook, and cluster runs on Union from both notebooks (run IDs in Verification above). Left: hosted **On this machine** for the scRNA notebook lacks `scikit-image` and `igraph`, ticket [[scrna-notebook-hosted-deps]]; `flyte.run` called directly from a workspace notebook still bundles from the SDK's directory, with `dispatch` as the supported path. No review comments.

Related: [[board]].
