---
title: The asset index runs on Postgres as well as SQLite
status: doing
priority: high
created: 2026-10-20
---

The first of three steps toward the hosted index on Aurora DSQL (ticket
`dsql-asset-index`): local, then the devbox (ticket `devbox-postgres-index`),
then Union. This one is the local story.

`SqliteIndex` and a new `PostgresIndex` share one implementation of the five
calls (`upsert`, `get`, `merge`, `delete`, `query`) and the same SQL. Only
what the engines spell differently stays in each class: the JSON column type
and accessor, the merge expression, and how a connection is opened and
writes are serialized. `make_index` returns a `PostgresIndex` for a
`postgresql://` URL. Local users see no change: the default stays
`~/.stargazer/index.db`.

The index tests that don't depend on SQLite's locking also run against
Postgres, in a new `postgres` test tier that starts a throwaway Postgres
container (Postgres 16, the version DSQL is compatible with).

- [x] `postgres` tier: the shared index tests against a Postgres container
- [x] One SQL implementation behind `SqliteIndex` and `PostgresIndex`
- [x] `make_index` dispatch for `postgresql://`
- [x] Docs: `configuration.md`, the index module's docstring

## Verified (2026-10-20, branch `feat/postgres-index`)

- **Postgres tier:** 10 passed against `postgres:16-alpine`, after the same
  tests failed against a stub (no `upsert`; `make_index` returned a
  `SqliteIndex`). The container is removed after the session.
- **Unit tier:** 497 passed.
- **Tasks tier:** 39 passed in the GATK/general image and 16 in the scRNA
  image, so the images' SQLite runs the new SQL (`RETURNING`,
  `json_patch`).
- **The scRNA notebook locally** (verify-stargazer, `scrna-pipeline`):
  export exit 0, `check_anndata.py` `ok` for both samples at every stage
  from raw to annotated, no warnings, 14 index rows. Evidence in
  `~/.stargazer/verify-runs/20261020-085147-pgindex/evidence/`.
- **Devbox dashboard and asset storage:** 5 passed (`pytest -m devbox
  tests/devbox/test_dashboard.py tests/devbox/test_asset_storage.py`). The
  dashboard serves its index from the refactored `SqliteIndex`.
