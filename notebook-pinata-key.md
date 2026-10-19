---
title: Give notebook pods the Pinata key as a secret
status: doing
priority: normal
created: 2026-10-18
---

Hosted notebook pods get the org's Pinata key, as a Flyte secret, the way
dashboards do (ticket `dashboard-pinata-key`). Without it a notebook sees
only the user's own store: public data doesn't join its queries, and
publishing a stored file from a notebook (ticket `publish-asset`) raises.
Tasks and dashboards already have the key, so any user can already reach it
from a task they run (decided 2026-10-18: "put the pinata key everywhere").

## Design

`per_notebook_env` declares `secrets=STARGAZER_SECRETS`, the same list the
task environments and the dashboard declare. Union injects it and keeps only
a reference in the app's spec (measured 2026-10-17, ticket
`dashboard-pinata-key`). The devbox drops app secrets, so a devbox notebook
still has no public tier.

## Pieces

- [ ] `app/per_notebook.py`: the secret on the notebook env. A test in
      `tests/unit/test_per_notebook.py`: the built env declares `PINATA_JWT`
      as a secret, and no env var holds it.
- [ ] Docstrings and docs that say notebook pods carry no credential:
      `app/per_notebook.py`, `app/config.py`,
      `docs/architecture/configuration.md`,
      `.opencode/reference/architecture/app_internals.md`,
      `.opencode/reference/devbox_workarounds.md`.
- [ ] Verify on Union with the test account: launch a notebook from a
      dashboard deployed from the branch, and in the pod the key is set
      (its length only) and Pinata accepts it; the app's spec holds only a
      reference. Stop every app the check started.
