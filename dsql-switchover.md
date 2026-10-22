---
title: Every dashboard switches its asset index to DSQL
status: done
priority: high
created: 2026-10-21
pr: 78
---

What ticket `dsql-asset-index` left after PR #77: the code to index on DSQL is in, and onboarding in infra makes each user's table, login and IAM role, but every user's dashboard still keeps its own SQLite index, because infra's `tenant.env` leaves `STARGAZER_DSQL_CLUSTER_ARN` commented out. Turning it on before their rows move would show every user an empty index.

## Pieces

- [x] **Migration:** for each Stargazer project, make its index (`stargazer_users.user_index.ensure_user_index`), restore its dashboard's Litestream replica (`<root>/users/<subject>/index`) once, and insert the rows into its DSQL table. Check the counts match.
- [x] **Switch:** uncomment `STARGAZER_DSQL_CLUSTER_ARN` in `tenant.env` and `./stargazer-users upgrade`.
- [x] **Removals** (stargazer, PR #78; infra `095066f`; the probe data deleted by the user):
  - Litestream: the image layer, and restore/replicate in `app/dashboard_launch.py`.
  - `app/index_api.py` and `HttpIndex`.
  - `refuse_while_running` in `app/deploy.py`, and the wait-for-runs loop in infra's `upgrade`: a redeploy no longer risks the index.
  - The PR #52 probe data under `stargazer-probe-revisions/` and `stargazer-probe-revisions-2/` in the bucket (about 300 objects; needs write access).
- [x] **Docs:** the Asset Index section of `docs/architecture/app.md`, `configuration.md`, `app_internals.md`, and the devbox recipe in `contributing.md` and `devbox/setup.sh`'s notes where they mention the dashboard's index.

**Verified when:**
- The germline workflow runs end to end on the test account.
- A dashboard redeploy while writes are going in costs no index call, since none reach the dashboard.
- A task in another project is refused on the user's table (measured for `DsqlIndex` already: `flytesnacks` fails at `AssumeRoleWithWebIdentity`).

## Migration and switch (2026-10-21)

- **One user to move.** The only active Stargazer project is `u-pryce` (the test account, subject `387300641116005877`), and the bucket holds one replica, `stargazer/users/387300641116005877/index/` (63 LTX files, newest 2026-10-22 00:44 UTC). Its table, login and IAM role were already made by the tenant check's `onboard`, so `ensure_user_index` had nothing to do.
- **Quiet first.** The dashboard was deactivated, already on its `dsql://` URL from the tenant check, every notebook app in the project was inactive and no run was going, so nothing could write to the SQLite index while it moved.
- **Restore,** read-only (`AWS_PROFILE=claude`): `litestream/litestream:0.5.17` in Docker, `restore -o u-pryce.db '…/users/387300641116005877/index?region=us-west-2'`. `PRAGMA integrity_check` ok, 43 rows in `assets` (verify notes, scRNA AnnData, sample sheets, cohort summaries, TUS probes).
- **Insert,** as the user's own login rather than the admin: a one-off task in `u-pryce` (run `ufjvmtbsrttf8zld5f6j`, SUCCEEDED, on the Piece 0 probe's image, a registry hit) assumed `stargazer-index-u-pryce` from its pod token as `DsqlIndex` does, inserted the 43 rows in one transaction with `ON CONFLICT (cid) DO NOTHING`, keeping each `created_at`, then reread the table. Its report: `source_rows 43, table_rows_before 0, table_rows_after 43`, `missing`, `differ` (uri, name, keyvalues, created_at) and `extra` all empty.
- **Switch:** infra `1000dee` uncomments the ARN in `tenant.env`. `./stargazer-users upgrade` under the `stargazer-upgrade` key (and `AWS_PROFILE=claude`: upgrade makes no AWS call) redeployed `u-pryce`'s dashboard at `ef05a1a` with `STARGAZER_INDEX_URL=dsql://u_pryce@ajufqlufrijtcts2ekxc4ovea4.dsql.us-west-2.on.aws/assets.u_pryce?role_arn=…stargazer-index-u-pryce`. Deactivated again afterwards.

## Removals, docs and verification (2026-10-22)

- **stargazer** `refactor/dsql-switchover` (PR #78, `c6b3dda`): Litestream, `app/dashboard_launch.py`, `app/index_api.py`, `HttpIndex`, `active_runs`, `refuse_while_running` and `STARGAZER_STORE_REGION` are gone. The dashboard starts with `exec uvicorn …`, the asset browser opens the index in `app.assets._get_index`, and notebook pods get the dashboard's own URL. `deploy_dashboard` refuses with no cluster ARN and no index in `extra_env`. Unit tier 518 passed, postgres tier 20 passed.
- **infra** `095066f` (pushed to `main` with `1000dee`): the index is always made and its role always deleted, `upgrade` has no wait-for-runs loop, onboard and upgrade refuse on Union without the ARN, and `STARGAZER_STORE_REGION` leaves `tenant.env`. 20 tests pass against stargazer `main` and against the branch.
- **Tenant, the branch's dashboard on the test account,** in Chrome as the owner: the private list returns the 43 migrated rows with their `created_at`, `/index/query` and `/index/assets/<cid>` return 404, and a TUS upload (`dsql-switchover-check.txt`, `bafkreichkco2mpk…`) lands in DSQL (44 rows).
- **Germline on DSQL:** seed `urvlfkkbrcvs6xrj2zlj`, workflow `ucj7rc9vqcq2h7h4xdvn` (11 actions, SUCCEEDED, `Variants(joint_call_gvcfs, cohort-dsql-192839, ['NA12829'], GRCh38)`), and a check from another pod, `uppfdv4gzdtcjjw7j9xn` (NA12829, 47 records on `chr17:7658421-7697490`).
- **Writes don't need the dashboard:** I deactivated it at 02:28:43 UTC, one second after the workflow started, and redeployed it at 02:29:56. Every action stored its outputs in between, the last finishing at 02:30:00 as the redeploy began; `haplotype_caller` and `joint_call_gvcfs` ran after the pod would have exited (30–50 s after deactivation, measured earlier).
- **Another project refused:** measured for `DsqlIndex` in PR #77 (`flytesnacks` fails at `AssumeRoleWithWebIdentity`).
- **Probe data deleted** by the user on 2026-10-22; both prefixes list 0 objects since (read-only check). Before: `stargazer-probe-revisions/` (75 objects) and `stargazer-probe-revisions-2/` (123), counted read-only. Deleting it needs write access: `aws s3 rm --recursive s3://union-us-west-2-stargazerbio/stargazer-probe-revisions/ --profile pryce`, then the same for `-2/`.

## Outcome

Shipped in PR #78 (merge `391df03`) with infra `1000dee` and `095066f`: every dashboard indexes in its user's DSQL table. The test account's 43 rows were migrated and checked field by field. Litestream, the dashboard's index API, `HttpIndex` and the wait-for-runs guard on redeploys are gone, and the probe data is deleted.

Verified on the tenant with the test account: the migrated rows listed in the dashboard, a TUS upload landing in DSQL, the germline workflow end to end on DSQL, and every action storing its outputs while the dashboard was down for a redeploy. Unit tier 518, postgres tier 20, infra 20. No comments on the PR.

Left: nothing.
