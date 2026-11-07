---
title: marimo-autoadd-headers
status: doing
priority: low
created: 2026-11-04
---

In a hosted notebook pod, running the Execution tutorial's cells made marimo add `flyte==2.12.4` to `execution.py`'s header with `pixi add --script`. The pod log shows `Adding to sandbox: /usr/local/bin/pixi add --script /stargazer/src/stargazer/notebooks/tutorials/execution.py --pypi flyte==2.12.4`. The file lives in `/stargazer`, so nothing is saved, but marimo rewrites a built-in notebook's header and may re-solve its environment on open, which would cost the prebuilt environment its speed.

To check:
- whether the uv sandbox did the same before pixi;
- whether the tutorials' headers should list `flyte` themselves, or marimo's package auto-add should be off in the pod.

Seen while verifying [[notebook-dockerignore]].

Related: [[board]], [[notebook-dockerignore]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
