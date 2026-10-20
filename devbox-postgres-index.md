---
title: The devbox's asset index moves to a Postgres pod
status: next
priority: high
created: 2026-10-20
blocked_by:
  - postgres-index
---

The second of three steps toward the hosted index on Aurora DSQL (ticket
`dsql-asset-index`). The devbox's index moves from the stand-in user's
dashboard to a Postgres deployment, reached by task and notebook pods
through `PostgresIndex` (ticket `postgres-index`).

- [ ] A Postgres deployment in `cli/devbox-setup.sh`, and its entry in
  `devbox_workarounds.md`
- [ ] The devbox dashboard and runs get the Postgres `STARGAZER_INDEX_URL`
  (`tests/devbox/conftest.py`, `contributing.md`'s devbox recipe)
- [ ] The devbox asset-storage and germline tests pass on it
- [ ] The `postgres` tier can run against the devbox's Postgres as well as a
  local container, if that turns out useful

Union keeps the dashboard-served index until `dsql-asset-index`, so nothing
is removed here.
