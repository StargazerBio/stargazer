---
title: The devbox's asset index moves to a Postgres pod
status: review
priority: high
created: 2026-10-20
pr: 60
---

The second of three steps toward the hosted index on Aurora DSQL (ticket
`dsql-asset-index`). The devbox's index moves from the stand-in user's
dashboard to a Postgres deployment, reached by task and notebook pods
through `PostgresIndex` (ticket `postgres-index`).

- [x] A Postgres deployment in `cli/devbox-setup.sh`, and its entry in
  `devbox_workarounds.md`
- [x] The devbox dashboard and runs get the Postgres `STARGAZER_INDEX_URL`
  (`tests/devbox/conftest.py`, `contributing.md`'s devbox recipe)
- [x] The devbox asset-storage and germline tests pass on it
- [x] The `postgres` tier can run against the devbox's Postgres as well as a
  local container, if that turns out useful: it doesn't. The tier's `index`
  fixture drops the `assets` table before every test, so it would wipe the
  devbox's index, and it would test the same `postgres:16-alpine` engine

Union keeps the dashboard-served index until `dsql-asset-index`, so nothing
is removed here.

## Verified (2026-10-20, branch `feat/devbox-postgres-index`)

- **Before:** with no Postgres deployed, the new storage test's pod failed
  with `failed to resolve host 'postgres.stargazer.svc.cluster.local'`.
- **`cli/devbox-setup.sh`:** exit 0 in 21 s, `✓ Postgres ready`; a second
  run left all four objects `unchanged`. The pod uses 53 MiB idle (256 MiB
  limit), PostgreSQL 16.15.
- **Devbox tier:** 8 passed (`pytest -m devbox -rP tests/devbox`, commit
  `82da062`, 2:33), including the germline workflow. The first run, on the
  switch-over deploy, failed `test_dashboard_lists_the_rows` once because
  Knative routed that request to the previous dashboard revision (still on
  SQLite).
- **Rows in Postgres:** every germline output, under
  `s3://flyte-data/stargazer/users/devbox-user/assets/`.
- **A notebook pod** launched from the devbox dashboard got the Postgres URL,
  and its sandbox Python read the task pods' `variants` rows through
  `PostgresIndex`.
- **Postgres tier:** 10 passed. **Unit tier:** 505 passed.
