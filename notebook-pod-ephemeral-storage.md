---
title: Execution tutorial edit pod evicted for disk use
status: next
priority: high
created: 2026-10-20
---

On Union, the Execution tutorial's edit pod never opens. Each pod is evicted about a minute after marimo's sandbox venv finishes installing, and the browser gets a Cloudflare 502. Measured 2026-10-20 in `u-pryce` (test account, dashboard at `89e637e`): two pods in a row, `nb-execution-edit-00001-deployment-847cc54fb6-fcp7s` and `-npfsj`, both with status reason `Evicted`, *"Pod ephemeral local storage usage exceeds the total limit of containers 1Gi."* The ReplicaSet was starting a third when the app was stopped. The pod log ends at `Installed 111 packages`, after numpy, matplotlib, pillow and marimo downloads.

The 1Gi isn't ours. The notebook container sets no ephemeral-storage limit, so the pod's total is the Knative `queue-proxy` sidecar's own limit (`ephemeral-storage: 1Gi`, request 512Mi; read with `kubectl get pod -o jsonpath`). The kernel venv, the uv cache and the hydrated workspace all live on that disk. The Workflows tutorial (`stargazer` only, 101 packages, no matplotlib) ran in the same project for more than 10 minutes without eviction, so heavier notebooks are the ones that tip over (inferred).

Likely fix: give the per-notebook app an explicit ephemeral-storage request and limit large enough for the venv plus the uv cache (`per_notebook_env` in `app/per_notebook.py`), if `flyte.Resources` or the app spec can express it. Otherwise, put the uv cache and venvs somewhere that doesn't count against the pod, such as an `emptyDir` with its own size. Check what Union allows before picking. Also measured: the notebook container's CPU is `100m` request and limit, because only memory is set when a notebook declares no resources. That probably explains the roughly 3-minute start before marimo serves (inferred). Size the CPU in the same change.

Verify by opening the Execution tutorial in Edit from the dashboard and leaving it open past the venv install. Ticket `hosted-notebook-flyte-init` needs that tutorial open to verify its fix.
