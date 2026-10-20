---
title: The hosted asset index moves to Aurora DSQL
status: backlog
priority: high
created: 2026-10-20
blocked_by:
  - assets-on-dashboard-home
  - devbox-postgres-index
---

On Union each user's asset index is a SQLite file on their dashboard pod,
served to task and notebook pods over HTTP and kept durable by Litestream.
The index is only as available as that one pod, which scales to zero and is
redeployed on every release. Making it survive redeploys took a lease beside
the replica, a ~13 s pause in which index calls get 502s, and
`refuse_while_running`, and left a broken release able to take the dashboard
down (PR #52, closed unmerged). Instead, the hosted index moves to Aurora
DSQL, and the dashboard drops out of the index path.

Locally nothing changes: `SqliteIndex` and `~/.stargazer/index.db` stay. The
devbox gets a plain Postgres pod. Local-to-cluster promotion stays out of
scope. The work goes in three steps: the shared SQL index (ticket
`postgres-index`), the devbox's Postgres pod (ticket
`devbox-postgres-index`), then this ticket, Union.

## Why DSQL

Decided 2026-10-20, over DynamoDB and Aurora Serverless v2:

- **One SQL implementation.** DSQL supports `jsonb` columns and all of
  Postgres's JSON functions and operators (DSQL docs, supported data types),
  so the hosted index shares its SQL with `SqliteIndex`; the JSON accessor
  differs (`->>` for `json_extract`). DynamoDB would mean a second
  implementation of the five calls and of the filter semantics.
- **Leaving AWS needs no rewrite.** Code written for DSQL's subset of
  Postgres runs on any Postgres.
- **Queries run on the server and reads are strongly consistent,** so a
  `companion_of` lookup in `fetch()` returns only matching rows and always
  sees the upstream task's write. On DynamoDB that lookup would read the
  whole partition, or use a secondary index that is only eventually
  consistent.
- **Per-user isolation is enforced by the database** (below), as
  `dynamodb:LeadingKeys` would have been.
- **No cold start and $0 idle** (AWS knowledge card), where Aurora
  Serverless v2 resumes from auto-pause in seconds or bills ~$45/month at
  0.5 ACU.

Costs, from the DSQL docs:
- **Optimistic concurrency.** A conflicting write gets a serialization error
  (SQLSTATE 40001) instead of waiting, so every write retries.
- **Connections time out after 1 hour.** Long-lived pods reconnect.
- **Transaction limits:** one DDL statement per transaction, at most 3,000
  rows per transaction.
- **The devbox can't catch DSQL-only failures.** Plain Postgres accepts a
  superset of what DSQL does, so those surface only on the tenant. I know of
  no local DSQL emulator.

## Per-user isolation without Union

Union's documented route to a per-project role is for Union's team to bind
it to the namespace
([BYOC: enabling AWS resources](https://www.union.ai/docs/v2/union/deployment/byoc/enabling-aws-resources.md)).
This doesn't need that.

**Measured 2026-10-20** (read-only: `AWS_PROFILE=claude`, kubectl through
`stargazer-eks-access`):
- The cluster uses IRSA. Its OIDC provider is registered in IAM
  (`oidc.eks.us-west-2.amazonaws.com/id/21AC1CCD151FDBB6668C69B23D6ED9E1`),
  `pod-identity-webhook` is installed, and the EKS Pod Identity add-on
  isn't.
- In all six `u-*` namespaces the `default` service account is annotated
  with `union-us-west-2-stargazerbio-userflyterole`, including the
  namespaces `stargazer-users onboard` created for the test account. Union
  sets new namespaces up without a request per project.
- Task and app pods both run as `default` and get the projected token.
  Audit-log pod specs for task pod `ujgbbqc4xtlwgbb2hjst-a0-0` and pod
  `dashboard-00003` in `u-pryce-development` carry `AWS_ROLE_ARN`,
  `AWS_WEB_IDENTITY_TOKEN_FILE` and a mount at
  `/var/run/secrets/eks.amazonaws.com/serviceaccount`.
- `u-pryce-development`'s `default` can't create `serviceaccounts/token` or
  pods, read secrets, or patch service accounts, in its own namespace or in
  the test account's (`kubectl auth can-i`).
- The shared role trusts `system:serviceaccount:*:*`.

**The mechanism** (standard IRSA, not yet tried here):
- A pod's token is signed by the cluster, and its `sub` names the pod's
  namespace.
- A role whose trust policy requires
  `sub = system:serviceaccount:<project>-development:default` and
  `aud = sts.amazonaws.com` can be assumed with `AssumeRoleWithWebIdentity`
  only from that namespace.
- Pods keep the shared role as their default credentials. Only the index
  client assumes the per-user role, using the same token file.
- The shared role has never had DSQL access, so nothing has to be taken away
  from it. That's what makes this work without Union where storage
  isolation doesn't (ticket `per-user-storage-isolation`).

**Not airtight while the org key is in every pod:** a pod can start a run in
another user's project, and that run carries that project's token (ticket
`org-wide-platform-key`).

## Design

- One DSQL cluster for the org, single-region, us-west-2, created once by
  hand.
- One schema per user, holding the same `assets` table `SqliteIndex`
  creates (keyvalues as `jsonb`). One database role per user, mapped to
  their IAM role with `AWS IAM GRANT`, holding `USAGE` on their schema
  only. DSQL manages permissions through schema-level grants.
- `STARGAZER_INDEX_URL` picks the backend in `make_index`: a file path
  (SQLite, unchanged), a Postgres URL (devbox), or a DSQL endpoint with
  schema and role (Union). The exact URL form is decided in the work.
- The dashboard's asset page uses the same index class as every other
  client.

## Pieces

- [ ] **Piece 0, the tenant check**, by hand, with the user's admin access
  (mine is read-only):
  - Create the cluster. For `u-pryce`, create the IAM role, the schema, the
    table, the database role and the grants.
  - From a task in `u-pryce-development`: assume the role from the token
    file, get a DSQL token, connect, upsert, and query by a keyvalue.
  - From a task in `flytesnacks`: `AssumeRoleWithWebIdentity` on
    `u-pryce`'s role is refused.
  - The shared role can't log in as `u-pryce`'s database role.
  - Confirm `INSERT … ON CONFLICT` and `->>` filters behave as in SQLite.
  - Time the assume, token and connect steps a task pays per call.
- [ ] **DSQL on `PostgresIndex`** (ticket `postgres-index`): connecting with
  a token from the assumed per-user role, retrying serialization errors, and
  reconnecting when a connection times out. `make_index` accepts the DSQL
  URL form.
- [ ] **Onboarding:**
  - `stargazer-users onboard` creates, on every call and safely when it
    already exists, the IAM role (trust as above, `dsql:DbConnect` on the
    cluster), then the schema, table, role and grants as the DSQL admin.
  - This needs the admin's AWS credentials (`iam:CreateRole`,
    `iam:PutRolePolicy`, `dsql:DbConnectAdmin`). Today onboarding needs
    only Flyte credentials. `upgrade` needs no AWS access.
  - `offboard` deletes the IAM role and keeps the schema, as it keeps the
    user's notebooks.
- [ ] **Deploys:** dashboards, notebook pods and the runs they start get
  the DSQL `STARGAZER_INDEX_URL`.
- [ ] **Migration:** each existing user's rows (the test account and
  `u-pryce`) are restored from their Litestream replica once and inserted.
- [ ] **Removals:**
  - Litestream: the image layer, and restore/replicate in
    `app/dashboard_launch.py`.
  - `app/index_api.py` and `HttpIndex`.
  - `refuse_while_running` and the retry loop in `upgrade`.
  - The PR #52 probe data under `stargazer-probe-revisions/` and
    `stargazer-probe-revisions-2/` in the bucket (about 300 objects; needs
    write access).
- [ ] **Docs:** the Asset Index section of `docs/architecture/app.md`,
  `configuration.md`, `app_internals.md`, `devbox_workarounds.md`,
  `contributing.md`'s devbox recipe.

**Verified when:**
- The germline workflow runs end to end on the test account.
- A dashboard redeploy while writes are going in costs no index call, since
  none reach the dashboard.
- A task in another project is refused on the user's schema.

## Meanwhile

`main` still has the bug PR #52 fixed. A redeploy runs the old and new
dashboard pods side by side, and both replicate to the same path (measured
2026-10-19, test account, throwaway root):
- The old pod rewrote L0 transaction 2 a minute after the new pod had
  uploaded its own, with no request reaching it.
- Both pods compacted the same files, with overlapping ranges.
- A write the old pod accepted was missing after a fresh restore.

`App.deactivate(wait=True)` returns while the pods take another 30–50 s to
exit. Until this ticket lands, stop a dashboard and wait about 90 s before
redeploying it (`onboard` re-runs and `upgrade`).
