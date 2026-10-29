---
title: dsql-test-tier
status: done
priority: normal
created: 2026-10-28
pr: 100
---

`DsqlIndex` (`src/stargazer/utils/index.py`) signs its own DSQL auth tokens, caches them and the user's assumed-role credentials, and sets up TLS and IPv4 itself. No test ran any of it: the postgres tier swaps `_connect` for a password login, so the only check was driving the tenant by hand. Everything else `DsqlIndex` does is `PostgresIndex`'s SQL and its 40001 retry, which the postgres tier covers, the retry under serializable isolation.

Swapping in AWS's connector was weighed and set aside: without its pool it makes every call slower. Ticket `dsql-connection-pool` has the measurements and what pooling would take.

## Plan

- [x] A `dsql` test tier: the index and state tests against the real cluster, as its admin, in a schema it makes and drops. On demand, with the admin's AWS session and infra's `tenant.env`, like the pinata tier with its key. A `dsql://` URL for `admin` needs no `role_arn` and signs with the caller's credentials; a user's login still needs its role.
- [x] Docs: the test tiers in the `write-tests` skill and `AGENTS.md`, the index client in `app_internals.md`.

## Verification

- The `dsql` tier passes against the cluster (measured: 17 passed; 20 concurrent merges met 47 conflicts, all `40001`, and every merge landed).
- Tenant, test account: the dashboard from the branch still reads the user's index and state table, as a user's login through their role.

## Outcome

Shipped in PR #100 (merge `356e514`): a `dsql` test tier (`tests/dsql/`) that runs the index and `app.user_state` tests through `DsqlIndex` against the real cluster, as its `admin`, in a schema each session makes and drops; an `admin` URL needs no `role_arn` and signs with the caller's own AWS credentials. Verified by the tier itself (17 passed on the cluster; a probe saw 20 concurrent merges of one row meet 47 `40001` conflicts, all retried), the unit (578), postgres (36) and infra (37) tests, and on Union with the test account's dashboard at `58e23ed` reading the user's index and state table through their role. Left: pooling the connection through AWS's connector, ticket `dsql-connection-pool` (`maybe`). No review comments.
