---
title: dsql-connection-pool
status: maybe
priority: low
created: 2026-10-28
---

`DsqlIndex` opens a new connection for every call, with its own cached IAM credentials and auth token, so a call is a TCP and TLS connect plus the query and no AWS calls. That's simple and never holds a connection past DSQL's one-hour limit, but every call pays for the connect. Worth revisiting as index traffic grows, the dashboard's first.

AWS's Aurora DSQL Connector for Python (`aurora-dsql-python-connector`, read at 0.2.7) only pays off with its pool. Its connect builds a new boto3 session and DSQL client and signs a fresh token every time, with no caching, so swapping it in under a connection per call makes every call slower. With its pool (`aurora_dsql_psycopg.create_pool`, `AuroraDSQLPool.run_transaction`) that cost is paid once per pooled connection, and a call is one round trip. `run_transaction` also retries conflicts (`OCCRetryConfig`; `is_occ_error` takes `40001`, `OC000` and `OC001`), which would replace `PostgresIndex.write`'s loop.

Measured from a laptop against the cluster, 2026-10-28:

- The connector's token step per connect (`TokenManager.get_token`, admin, SSO profile): 536 ms.
- Signing with an already-built DSQL client: 26 ms. `DsqlIndex` signs at most once per 10 minutes.
- A whole `DsqlIndex.get`, connect included: 234 ms from the laptop, mostly the connect's round trips to us-west-2. Pods in the region measured 21–41 ms per call before.
- 20 concurrent merges of one row: 47 conflicts, all SQLSTATE `40001`, all retried.

What adopting the pool takes:

- Pool lifecycle in every process that opens the index (dashboard, notebook pods, task pods): background threads, `max_lifetime` under 3600 s, and dropping connections DSQL has closed.
- The assumed role as a botocore `CredentialProvider` that keeps its credentials between connects; the connector inserts it into a new session each time.
- TLS and IPv4 stay ours: the connector passes `sslmode`, `sslrootcert`, `hostaddr` and `sslnegotiation` through to psycopg as given.
- A new seam for tests: infra's and the postgres tier's tests replace `DsqlIndex._connect`.
- The dsql test tier (ticket `dsql-test-tier`) runs before and after, with per-call latency measured in a pod.
