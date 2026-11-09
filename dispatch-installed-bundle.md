---
title: dispatch-installed-bundle
status: doing
priority: high
created: 2026-11-09
---

In a hosted notebook, where the SDK is an installed package since PR 135, `dispatch(where, task, ...)` set to "On the cluster" fails for a task imported from the SDK, the built-in tutorials' among them: `CodeBundleError: No files found to bundle in '…/site-packages'`. `ui.dispatch` overrides the run's root with `_bundle_root(task)`, the directory the task's module was imported from, which for an installed module is site-packages, and Flyte never bundles there. `config._bundle_root()` already says what the root should be once installed (the running notebook's folder), but `dispatch`'s override wins.

Measured on the tenant on 2026-11-09, as the test account, on `ghcr.io/stargazerbio/debug:run-modes` (main plus run-modes): the Execution tutorial in edit mode, `dispatch` of `audit_cohorts` "On the cluster" raised it, while `flyte.with_runcontext(mode="remote").run(audit_cohorts, ...)` from the same kernel succeeded (run `ulngbp5f75n9blfqwf6w`). `ui.py`'s bundling is unchanged from main, so main has it too. A workspace notebook's own tasks aren't hit: their module is the notebook, whose folder is `/workspace`.

Fix: `dispatch` takes `_bundle_root(task)` only when the task's module isn't inside an installed package (or only for a checkout and `__main__`), and otherwise leaves `init_flyte()`'s root. Verify with the same Execution tutorial cell on a hosted pod, and a workspace notebook's own task, both "On the cluster".

Related: [[board]], [[released-sdk-in-notebooks]], [[run-modes]].
