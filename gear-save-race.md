---
title: A running pod's save can overwrite a gear edit
status: backlog
priority: low
created: 2026-10-21
---

The gear on a workspace tile rewrites a notebook's stored setup block while a running pod of that notebook holds its own copy. If the pod's save later stores its copy, the gear's change is lost. That's inferred from the code, not reproduced (ticket `notebook-environment`).

Reproduce it first, on Union: edit a running notebook in its pod, change `main_env` from the gear, then let the pod's interval save run, and check which setup block is stored. If the gear's edit is lost, the fix might be the gear refusing while the notebook's pod is up, or the pod's save skipping a file that changed in the store since it hydrated.
