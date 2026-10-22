---
title: Every dashboard switches its asset index to DSQL
status: next
priority: high
created: 2026-10-21
---

What ticket `dsql-asset-index` left after PR #77: the code to index on DSQL is in, and onboarding in infra makes each user's table, login and IAM role, but every user's dashboard still keeps its own SQLite index, because infra's `tenant.env` leaves `STARGAZER_DSQL_CLUSTER_ARN` commented out. Turning it on before their rows move would show every user an empty index.

## Pieces

- [ ] **Migration** (infra, as the admin): for each Stargazer project, make its index (`stargazer_users.user_index.ensure_user_index`), restore its dashboard's Litestream replica (`<root>/users/<subject>/index`) once, and insert the rows into its DSQL table. Check the counts match.
- [ ] **Switch:** uncomment `STARGAZER_DSQL_CLUSTER_ARN` in `tenant.env` and `./stargazer-users upgrade`.
- [ ] **Removals** (stargazer):
  - Litestream: the image layer, and restore/replicate in `app/dashboard_launch.py`.
  - `app/index_api.py` and `HttpIndex`.
  - `refuse_while_running` in `app/deploy.py`, and the wait-for-runs loop in infra's `upgrade`: a redeploy no longer risks the index.
  - The PR #52 probe data under `stargazer-probe-revisions/` and `stargazer-probe-revisions-2/` in the bucket (about 300 objects; needs write access).
- [ ] **Docs:** the Asset Index section of `docs/architecture/app.md`, `configuration.md`, `app_internals.md`, and the devbox recipe in `contributing.md` and `devbox/setup.sh`'s notes where they mention the dashboard's index.

**Verified when:**
- The germline workflow runs end to end on the test account.
- A dashboard redeploy while writes are going in costs no index call, since none reach the dashboard.
- A task in another project is refused on the user's table (measured for `DsqlIndex` already: `flytesnacks` fails at `AssumeRoleWithWebIdentity`).
