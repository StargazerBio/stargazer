---
title: teardown-lists-no-apps
status: review
priority: normal
created: 2026-11-18
pr: 43
---

Infra's `verify-dashboard` helper `union_dashboard.py teardown` reports
`stopped: []` while the test account's dashboard is running, so a check
that trusts it leaves the dashboard's pod and node up for its whole
`scaledown_after`. Measured 2026-11-18 from a local checkout:
`dashboard-00003` was serving in `u-pryce-development`, and the helper
stopped nothing. `flyte update app dashboard --deactivate` by name stopped
it.

Cause: `app.per_notebook.list_project_apps` scopes its list request with
`get_init_config().org`, which is `None` under the config-file init
(`app.init.init` with `.flyte/union.yaml`), so the project-scoped list comes
back empty. The same function backs `/launch/status`, `/workspace/cleanup`
and `deploy.stop_project_apps`. In a pod, where init uses the API key, the
org is presumably set, but that isn't measured.

Fix: take the org from wherever the config-file init does keep it (or from
the endpoint) when the init config has none. Check the fix by running
`union_dashboard.py teardown` locally against a running test dashboard, and
confirm the in-pod callers still list apps.

## Cause, as measured

The org guess above was wrong: under the config-file init `get_init_config().org` is `stargazerbio`, and `list_project_apps` listed all 11 of `u-pryce`'s apps. The miss is in `app.deploy.stop_project_apps`, which picked apps by `App.is_active()`, true only for `ACTIVE` and `STARTED`. An app on its way up reads `UNASSIGNED`, `ASSIGNED` or `DEPLOYING` with desired state `STARTED`, and was skipped. The fix (infra PR 43) stops every app whose desired state isn't `STOPPED`. It also covers `pause` and `offboard`, which call the same function.

## Verification recipe

From an infra checkout with `tenant.env` loaded and the Union login:

1. Activate a stopped probe in `u-pryce` (`App.get(name="hdr-probe", project="u-pryce", domain="development").activate(wait=False)`), and while it reads anything but `ACTIVE`/`STARTED`/`STOPPED`/`UNASSIGNED`, call `app.deploy.stop_project_apps("u-pryce")`. It must return the probe, and the probe's desired state must read `DESIRED_STATE_STOPPED`. On `main` before the fix it returned `['dashboard']` with the probe `DEPLOYING`.
2. Activate the test dashboard the same way and at once run `union_dashboard.py teardown`: `stopped: ['dashboard']`, `live runs: []` (measured, with the dashboard at `UNASSIGNED`, desired `STARTED`).
3. Confirm every app in `u-pryce` reads desired state `STOPPED` and no run is live.

Related: [[board]], [[private-pinata-key]] (where it turned up).
