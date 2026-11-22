---
title: notebook-scaledown-setting
status: review
priority: normal
created: 2026-11-22
pr: 47
---

A notebook pod kept running a fixed 30 minutes after its last connection closed (infra `app/per_notebook.py`, `scaledown_after`). Users choose it now, in the dashboard's Settings modal beside the save interval: "Keep running for N minutes", 5 to 120, 30 by default. Coming back within it finds the session as it was; after it the pod scales to zero and the next open starts fresh. The dashboard's own scale-down (an hour, set at deploy) stays fixed: changing it would mean the dashboard redeploying itself, for a ~2.5 s cold start.

## Plan

- [x] `notebook_idle_minutes` setting in infra `app/settings.py`, its own state row, bounded server-side (`IDLE_MINUTES_MIN`/`_MAX`). `POST /settings` keeps a field left out as saved, and stores neither field when one is invalid, a blank included.
- [x] `/launch` passes it to `per_notebook_env` as `scaledown_after`, read at launch like the save interval.
- [x] The Settings modal's field and wording; `docs/architecture/app.md` and the internals reference.
- [x] On the tenant: the saved value reaches the served app's spec, and an idle pod stops after it. Measured 2026-11-22 on the test account's dashboard at `2026.11.18.1-4a0d819` (infra PR 47): Keep running saved at 10 through the modal, 500 refused with a 400, `nb-agent-mcp-probe-edit` served with `scaledown_period: 600s` (the dashboard's stayed 3600 s), ready at 18:21:49 UTC with no tab open and "Scaled to zero" at 18:31:46.

## Verification recipe

1. `uv run pytest tests/unit/test_app.py tests/unit/test_per_notebook.py` in infra.
2. Deploy the test account's dashboard from the branch (`verify-dashboard`'s `union_dashboard.py deploy`), open Settings, set Keep running to 10, Save. POST `/settings` with `notebook_idle_minutes=500` from the page: 400.
3. Launch a workspace notebook (`fetch('/launch', ...)` from the dashboard page), then read the app's spec: `App.get(name="nb-<slug>-edit", project="u-pryce").pb2.spec.autoscaling.scaledown_period` is 600 s; the dashboard's stays 3600 s.
4. With no tab open on it, watch the pod (`KUBECONFIG=~/.kube/union kubectl get pods -n u-pryce-development`, read-only): it terminates about 10 minutes after it was ready.
5. Put Keep running back to 30 and tear down (`union_dashboard.py teardown`).

Related: [[board]], [[notebook-ws-timeout]].
