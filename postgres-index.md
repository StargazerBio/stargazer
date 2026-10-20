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

- [ ] `postgres` tier: the shared index tests against a Postgres container
- [ ] One SQL implementation behind `SqliteIndex` and `PostgresIndex`
- [ ] `make_index` dispatch for `postgresql://`
- [ ] Docs: `configuration.md`, the index module's docstring
