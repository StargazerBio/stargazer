---
title: Stage the image's notebooks as /opt/notebooks
status: doing
priority: high
created: 2026-10-20
---

Follow-up to ticket `quickstart-save-banner`, whose last commit missed the
merge of #56. The `Dockerfile` stages the SDK's notebooks folder at
`/opt/workspace/notebooks` (a `mkdir`ed wrapper) and copies
`/opt/workspace/.` into `/workspace`. Staging it as `/opt/notebooks` and
running `cp -rn /opt/notebooks /workspace/` lands the same
`/workspace/notebooks/`, with no wrapper.

On `fix/notebooks-staging` (`4665a1f`, cherry-picked from `41c03a4`), no PR
yet.

## Verified (2026-10-20, on `41c03a4`, same `Dockerfile`)

A fresh start has `notebooks/{templates,tutorials,workflows}/` with all
seven notebooks. With a host directory mounted at `/workspace` that already
had an edited `notebooks/tutorials/assets.py`, the edit was kept, the other
six were added beside it, and there was no nested `notebooks/notebooks/`.
