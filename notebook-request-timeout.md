---
title: notebook-request-timeout
status: review
priority: normal
created: 2026-11-22
pr: 48
---

The platform cuts every request to a notebook pod at its app's request timeout, an open websocket included, and the notebook apps (infra `app/per_notebook.py`) set none, so the five-minute default closed the terminal and the agent panel's sessions every five minutes. Notebook pods now set 20 minutes (`NOTEBOOK_REQUEST_TIMEOUT`); Flyte allows at most an hour. It doesn't change when a pod scales to zero, since a closed tab's connections end either way. It does raise the pod's termination grace period to 20 minutes, which only a hung shutdown would use.

## Plan

- [x] `timeouts=flyte.app.Timeouts(request=NOTEBOOK_REQUEST_TIMEOUT)` on every notebook app; the internals reference.
- [x] On the tenant: the spec and the Knative service carry 1200 s, sockets survive past five minutes, and a pod with sockets open still stops quickly. Measured 2026-11-22 on the test account at `2026.11.18.1-550c5c8` (infra PR 48): `timeoutSeconds: 1200`, the pod's grace period 1200 s (the dashboard's 300 s); the session and agent sockets open from 18:39:26 to past 18:46:51 UTC with no close and no queue-proxy timeout; deactivated with both open, the pod was gone in 53 s.

Conflicts with infra PR 47 on adjacent lines of `app/per_notebook.py`; whichever merges second is rebased. Stargazer PR 171's handover still runs every four minutes, more often than this needs.

## Verification recipe

1. Deploy the test account's dashboard from the branch (`verify-dashboard`'s `union_dashboard.py deploy`) and launch a notebook in edit mode.
2. Read-only kubectl (`KUBECONFIG=~/.kube/union`, `-n u-pryce-development`): `get ksvc nb-<slug>-edit -o jsonpath='{.spec.template.spec.timeoutSeconds}'` is 1200, and the pod's `terminationGracePeriodSeconds` is 1200.
3. Open the notebook in the browser and wait seven minutes. The notebook container's log shows the `/ws` and `/__sg__/agent/<name>` sockets accepted once and never closed, and queue-proxy logs no timeout.
4. `flyte --config .flyte/union.yaml update app nb-<slug>-edit --deactivate -p u-pryce -d development` with the tab open: the pod is gone within about a minute.
5. Tear down: `union_dashboard.py teardown`.

Related: [[board]], [[notebook-ws-timeout]], [[notebook-scaledown-setting]].
