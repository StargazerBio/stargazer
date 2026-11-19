---
title: teardown-lists-no-apps
status: doing
priority: normal
created: 2026-11-18
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

Related: [[board]], [[private-pinata-key]] (where it turned up).
