---
title: The DSQL index connects through AWS's connector, with a test tier on real DSQL
status: doing
priority: normal
created: 2026-10-28
---

`DsqlIndex` (`src/stargazer/utils/index.py`) signs its own DSQL auth tokens, caches them and the user's assumed-role credentials, and sets up TLS and IPv4 itself. AWS ships that as the Aurora DSQL Connector for Python (`aurora-dsql-python-connector`, an auth plugin over psycopg). No test runs any of it: the postgres tier swaps `_connect` for a password login, so the only check is driving the tenant by hand. Everything else `DsqlIndex` does is `PostgresIndex`'s SQL and its 40001 retry, which the postgres tier covers, the retry under serializable isolation.

## Plan

- [ ] `DsqlIndex._connect` connects through `aurora_dsql_psycopg`, with the user's assumed role as its credentials provider. Our token signing and caching go. `_connect(autocommit)` stays the seam, since infra's tests override it. The 40001 retry stays: the Python connector doesn't retry.
- [ ] A `dsql` test tier: the index tests against the real cluster, as its admin, in a throwaway schema it drops afterwards. It covers what Postgres can't: the connector's auth and TLS, and the retry under DSQL's own optimistic concurrency. On demand, with the admin's AWS session, like the pinata tier with its key.
- [ ] Docs: the index's DSQL section in `app_internals.md`, the test tiers in the `write-tests` skill and `AGENTS.md`.

## Verification

- The `dsql` tier passes against the cluster, before the swap (our code) and after (the connector).
- Tenant, test account: the dashboard from the branch reads and writes the user's index and state table (asset explorer's Mine, a launch), and a task pod writes to the index, so the assumed role works from both pods.
