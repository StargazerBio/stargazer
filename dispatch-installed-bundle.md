---
title: dispatch-installed-bundle
status: review
priority: high
created: 2026-11-09
pr: 138
---

In a hosted notebook, where the SDK is an installed package since PR 135, `dispatch(where, task, ...)` set to "On the cluster" fails for a task imported from the SDK, the built-in tutorials' among them: `CodeBundleError: No files found to bundle in '…/site-packages'`. `ui.dispatch` overrides the run's root with `_bundle_root(task)`, the directory the task's module was imported from, which for an installed module is site-packages, and Flyte never bundles there. `config._bundle_root()` already says what the root should be once installed (the running notebook's folder), but `dispatch`'s override wins.

Measured on the tenant on 2026-11-09, as the test account, on `ghcr.io/stargazerbio/debug:run-modes` (main plus run-modes): the Execution tutorial in edit mode, `dispatch` of `audit_cohorts` "On the cluster" raised it, while `flyte.with_runcontext(mode="remote").run(audit_cohorts, ...)` from the same kernel succeeded (run `ulngbp5f75n9blfqwf6w`). `ui.py`'s bundling is unchanged from main, so main has it too. A workspace notebook's own tasks aren't hit: their module is the notebook, whose folder is `/workspace`.

Fix: `dispatch` takes `_bundle_root(task)` only when the task's module isn't inside an installed package (or only for a checkout and `__main__`), and otherwise leaves `init_flyte()`'s root. Verify with the same Execution tutorial cell on a hosted pod, and a workspace notebook's own task, both "On the cluster".


## Verification recipe

DISPATCH-INSTALLED: in a hosted pod, `dispatch` "On the cluster" of a task imported from the installed SDK submits a run that bundles the running notebook's folder.

1. Build the branch's image and push it as `ghcr.io/stargazerbio/debug:<slug>` (`docker buildx build --platform linux/amd64 -f runtime/Dockerfile -t … --push .`). Deploy the test account's dashboard on it from the infra checkout: `STARGAZER_NOTEBOOK_IMAGE=<image> uv run python .claude/skills/verify-dashboard/scripts/union_dashboard.py deploy` with `tenant.env` loaded.
2. From the dashboard page in the built-in browser, `POST /launch` with `slug=execution`, `mode=edit`, `section=tutorials`, and open the URL it returns. Run all cells.
3. Add a cell and run it:

   ```python
   from types import SimpleNamespace as _NS; import stargazer as _sg; from stargazer.notebooks.ui import dispatch as _dispatch; _out = await _dispatch(_NS(value="remote"), audit_cohorts, sheets=sheets); print("RESULT", _sg.__file__, len(_out))
   ```

   Passes: the cell's log shows `Code bundle: <n> files` and `Waiting for run '<name>'`, with no `CodeBundleError`. Fails as on `main`: `CodeBundleError: No files found to bundle in '…/site-packages'`.
4. Redeploy the dashboard without `STARGAZER_NOTEBOOK_IMAGE`, run `union_dashboard.py teardown`, deactivate the dashboard, and confirm no active app and no live run in `u-pryce`.

Gotcha: on `main` before PR 137, a tutorial's tasks run on the published `stargazer-core`, which is private, so the submitted run fails while initializing whatever the bundle. Judge this check by submission, or run it on a branch that includes PR 137.

## Evidence (2026-11-09)

- Unit tier: 282 passed. The installed-SDK test failed before the fix (`…/src` instead of the notebook's folder).
- Hosted pod on `ghcr.io/stargazerbio/debug:dispatch-installed-bundle` (`sha256:6eb66a90…`): `dispatch` "On the cluster" of `audit_cohorts` bundled 4 files and submitted run `u8849z8657x4xnhbn6sp`, with no `CodeBundleError` (measured). The run failed while initializing, as the tutorial's own `flyte.run` cells did. The inferred cause is the private `stargazer-core:2026.10.30` (anonymous manifest request: 403).
- Torn down: dashboard back on its release, then stopped; no active app and no live run in `u-pryce`.

PR 138's commits are merged into `feat/run-modes` (PR 137), since both rewrite `dispatch`: merging 137 lands the fix, and 138 closes then.

Related: [[board]], [[released-sdk-in-notebooks]], [[run-modes]].
