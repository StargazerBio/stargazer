---
title: A launch's image build survives a dashboard restart
status: next
priority: high
created: 2026-10-27
---

A launch whose declared image isn't built yet answers 202 and builds in the background (PR #89). What it's waiting on lives only in the dashboard process: `_builds` in `app/admin_app.py`, and an asyncio task (`_serve_when_built`) that serves the pod when the build finishes. A dashboard restart drops both. The build finishes, but the pod is never served and a failure is never reported: `/launch/status` reports the notebook as neither building nor running, and `launch.js` gives up after 60 empty polls and hands the buttons back without a word (inferred from the code, not reproduced). Since PR #78 `upgrade` redeploys dashboards without waiting for anything, so a redeploy during a user's build is an ordinary event.

Each user's DSQL index is always there, so the launch's state moves into it, and `/launch/status`, which the page already polls every 5 s, settles it.

## Plan

- [ ] **A per-user state table.** One table per user beside their index table, `key TEXT PRIMARY KEY, value TEXT, updated_at`, for the dashboard's own per-user state (this ticket's launches, then ticket `settings-in-state-table`). Its name comes from the index table's (e.g. `assets.u_jane_state` for `assets.u_jane`), so a deploy passes nothing new.
  - SDK: its DDL beside `postgres_table_sql` in `stargazer.utils.index`. `PostgresIndex` makes it itself, as it makes the index table, so the devbox needs nothing; `DsqlIndex` still never runs DDL.
  - Infra: `ensure_table_and_login` makes it and grants the login row privileges on it.
  - Infra: `upgrade` calls `ensure_user_index` before each deploy, so table changes roll out with the code. `upgrade` then needs the admin's AWS credentials, which `tenant.env` already names.
  - App: a small module (e.g. `app/user_state.py`) with get, set, delete and list-by-prefix, on the index's connection and its rerun on serialization failure (SQLSTATE 40001). Make public what it needs from the index rather than reaching into `_connect` and `_write`.
- [ ] **`/launch`** writes the pending launch as one row, key `launch:<slug>:<mode>`, value the build run's name and the image URI, and answers 202 as today. A launch while that row is pending answers the same 202.
- [ ] **`/launch/status`** reads the pending rows. For each, the build run's phase decides:
  - running: reported as `building`, as today.
  - succeeded: rebuild the notebook's environment from its stored source (as `/launch` does), serve it on `flyte.Image.from_base(<uri>)`, which skips Flyte's build check, and delete the row. Delete first, conditionally, so only the poll that deleted it serves.
  - failed: keep the reason in the row and report it as `failed` until the notebook is launched again.
- [ ] **Removed:** `_Build`, `_builds`, `_serve_when_built`, and `_forget_build` with its import of Flyte's private `ImageBuildEngine` caches.
- [ ] **Docs:** the launch section of `docs/architecture/app.md` and `app_internals.md`, the index and state tables in the Asset Index section, and the module docstrings touched.

## Verification

- Tests first: a pending launch is reported as building by a fresh process (module state cleared); a succeeded run is served once and its row deleted; a failed run reports its reason until the next launch. Postgres tier: the state table on a login with only row privileges on it.
- Tenant, test account: launch a workspace notebook whose `main_env` layers a new package, run `./stargazer-users upgrade` while it builds, and the pod comes up once the build finishes. Then a `main_env` with a package that doesn't exist: the failure reaches the page after a redeploy mid-build too.
