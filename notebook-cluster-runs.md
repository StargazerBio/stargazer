---
title: Cluster runs for notebook-defined workflows
status: backlog
priority: normal
created: 2026-10-20
blocked_by:
  - local-remote-toggle
  - qc-filter-organism-from-asset
---

The scRNA notebook and the `basic` template define their workflows in regular cells and await them in-process. A cluster can't run those: Flyte's task pod imports the notebook module and looks the task up as an attribute, and importing a marimo notebook runs its setup block and `@app.function` cells, not its regular cells. Measured 2026-10-20 with a throwaway notebook, resolving a task the way a pod does: defined in a cell, `AttributeError: module 'cell_task' has no attribute 'cell_task'`; the same task as `@app.function` over `@env.task`, loaded. The Execution tutorial already submits its remote run that way, importing `audit_cohorts` from the Workflows tutorial, where it's an `@app.function`.

The `basic` template's Run section also says `flyte.run(my_workflow, ...)` reaches a remote endpoint once one is configured, which the above says it wouldn't.

To do, per notebook: move the workflow (and the env, task and asset it needs) into the setup block and `@app.function` / `@app.class_definition` cells, check the env's image has what the task imports (the template's `my_env` has no image, so a pod gets Flyte's base image without stargazer), then swap the await for the `run_location()` control and `dispatch()` from ticket `local-remote-toggle`. Verify with one real cluster run each. The scRNA notebook's workflows also change with ticket `qc-filter-organism-from-asset`, which goes first.
