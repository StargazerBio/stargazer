---
title: A launch's image build survives a dashboard restart
status: done
priority: high
created: 2026-10-27
pr: 99
---

A launch whose declared image isn't built yet answers 202 and builds in the background (PR #89). What it's waiting on lives only in the dashboard process: `_builds` in `app/admin_app.py`, and an asyncio task (`_serve_when_built`) that serves the pod when the build finishes. A dashboard restart drops both. The build finishes, but the pod is never served and a failure is never reported: `/launch/status` reports the notebook as neither building nor running, and `launch.js` gives up after 60 empty polls and hands the buttons back without a word (inferred from the code, not reproduced). Since PR #78 `upgrade` redeploys dashboards without waiting for anything, so a redeploy during a user's build is an ordinary event.

Each user's DSQL index is always there, so the launch's state moves into it, and `/launch/status`, which the page already polls every 5 s, settles it.

## Plan

- [x] **A per-user state table.** One table per user beside their index table, `key TEXT PRIMARY KEY, value TEXT, updated_at`, for the dashboard's own per-user state (this ticket's launches, then ticket `settings-in-state-table`). Its name comes from the index table's (e.g. `assets.u_jane_state` for `assets.u_jane`), so a deploy passes nothing new.
  - SDK: its DDL beside `postgres_table_sql` in `stargazer.utils.index`. `PostgresIndex` makes it itself, as it makes the index table, so the devbox needs nothing; `DsqlIndex` still never runs DDL.
  - Infra: `ensure_table_and_login` makes it and grants the login row privileges on it.
  - Infra: `upgrade` calls `ensure_user_index` before each deploy, so table changes roll out with the code. `upgrade` then needs the admin's AWS credentials, which `tenant.env` already names.
  - App: a small module (e.g. `app/user_state.py`) with get, set, delete and list-by-prefix, on the index's connection and its rerun on serialization failure (SQLSTATE 40001). Make public what it needs from the index rather than reaching into `_connect` and `_write`.
- [x] **`/launch`** writes the pending launch as one row, key `launch:<slug>:<mode>`, value the build run's name and the image URI, and answers 202 as today. A launch while that row is pending answers the same 202.
- [x] **`/launch/status`** reads the pending rows. For each, the build run's phase decides:
  - running: reported as `building`, as today.
  - succeeded: rebuild the notebook's environment from its stored source (as `/launch` does), serve it on `flyte.Image.from_base(<uri>)`, which skips Flyte's build check, and delete the row. Delete first, conditionally, so only the poll that deleted it serves.
  - failed: keep the reason in the row and report it as `failed` until the notebook is launched again.
- [x] **Removed:** `_Build`, `_builds`, `_serve_when_built`, and `_forget_build` with its import of Flyte's private `ImageBuildEngine` caches.
- [x] **Docs:** the launch section of `docs/architecture/app.md` and `app_internals.md`, the index and state tables in the Asset Index section, and the module docstrings touched.

## Verification

- Tests first: a pending launch is reported as building by a fresh process (module state cleared); a succeeded run is served once and its row deleted; a failed run reports its reason until the next launch. Postgres tier: the state table on a login with only row privileges on it.
- Tenant, test account: launch a workspace notebook whose `main_env` layers a new package, run `./stargazer-users upgrade` while it builds, and the pod comes up once the build finishes. Then a `main_env` with a package that doesn't exist: the failure reaches the page after a redeploy mid-build too.

## As built

Five departures from the plan, each for a reason found while building or in review:

- **No `from_base` URI.** On Union the image's registry is unset and the remote builder picks it, so the URI isn't known until the build has finished. On success, the poll that claims the row runs the launch path again (`_launch`). Its build check now finds the image and serves it, with one image-service call. The row holds the run's name and URL and the notebook's section.
- **`_forget_build` stays**, called when Flyte's cache hands a launch a build run that has since finished (`Run.get`). The cache would otherwise hand a launch after a failed build the same failed run, so it would never build again in that process. While the run is still going, the cache is what lets the other mode or a second tab share it, so it isn't dropped on every launch. It still imports `flyte._internal`.
- **The serve after the build runs in the background** (`_serving`). `serve.aio` watches the app until it's ready, which can take minutes, too long to hold a status poll. So success doesn't delete the row: the poll claims it as `serving` (a conditional update), and it goes once the serve settles. A `serving` row with no task in the current process was claimed by a dashboard that restarted, and is claimed again.
- **Only an open page serves.** Nothing polls without one, so a build that finishes with no dashboard page open is served when the next page loads (`hydrateLaunches` polls once).
- **Infra `resume` ensures the index too.** `upgrade` skips paused users, so a user paused across this rollout would resume onto a dashboard with no state table.

The infra change (`ensure_table_and_login` makes and grants the state table; `upgrade` and `resume` call `ensure_user_index` before deploying; `AGENTS.md`) is stashed in the infra repo as `launch-build-state: state table + upgrade/resume ensure index`. It imports `state_table_sql` from stargazer, so it's applied and committed to infra's `main` only after this PR merges. Until then infra's `main` keeps working against stargazer's `main`.

## Verification recipe: a launch's build across a dashboard restart

A workspace notebook whose `main_env` needs an image that isn't built yet shows as building. Redeploying the dashboard while the image builds doesn't lose the launch: the pod comes up when the build finishes. A build that fails is reported on the page even after a redeploy.

### Sub-features

- **R1** A pending launch is reported building by a freshly deployed dashboard.
- **R2** Once the build succeeds, the pod is served once, and the tile shows Open and Stop.
- **R3** A failed build's reason reaches the page after a mid-build redeploy, until the next launch.

### How to get to it (user POV)

Workspace tile, then Edit, on a notebook whose setup block layers a new package onto `notebook_base`.

### Driving it

Preconditions: `aws sso login --profile pryce`, then apply infra's stash and point infra at this worktree. The test account's index has to get its state table before its dashboard is served. `ensure_user_index` alone does that without re-onboarding; restore infra's checkout afterwards (`git checkout -- .`, the stash stays).

```bash
cd ../infra && git stash apply <sha>
PYTHONPATH="$W:$W/src" uv run -q --project . --env-file tenant.env python -c "from stargazer_users.user_index import ensure_user_index; ensure_user_index('u-pryce')"
```

1. Create a workspace notebook whose `main_env` is `notebook_env.clone_with(name="lbs", image=notebook_base.with_pip_packages("<a package no image has yet>"))`. Click Edit. Pass: the tile shows the build link.
2. Mid-build, restart the dashboard: `flyte --config .flyte/union.yaml update app dashboard --deactivate -p u-pryce -d development`, wait until it's inactive, then `--activate`. Pass: once it's up, `/launch/status` from the page reports the build, and the tile still shows the build link (R1).
3. Wait for the build. Pass: within one poll of the run succeeding, the tile shows Open and Stop, and `union_dashboard.py check nb-<slug>-edit` serves the new image (R2).
4. Repeat with a second notebook whose `main_env` is `notebook_base.with_commands(["sleep 120 && false"])`, restarting mid-build. Pass: the watching tab alerts "Launch failed: This notebook's image failed to build: …" with the build's output, and `/launch/status` keeps reporting it failed (R3).
5. `union_dashboard.py teardown`. Pass: live runs `[]`.

### Gotchas

- The AWS SSO session expires; `aws sso login --profile pryce` before onboarding.
- Never `stargazer-users upgrade` from the branch: it redeploys every user's dashboard.
- `union_dashboard.py deploy` of an unchanged commit may not restart the pod, so it isn't a restart; deactivate and activate the app instead.
- A pip package that doesn't exist fails the build in under a second, too fast to restart in between; a `sleep` in `with_commands` gives a slow failure.
- `Run.get` from a local shell needs `flyte.init_from_config(..., project='u-pryce')`: the default project is `flytesnacks`.


## Outcome

Shipped in PR #99 (merge `af99f11`): a per-user state table beside each index table (`app/user_state.py` on `SqlIndex.read`/`write`), and a pending launch is a row in it that `/launch/status` settles by its build run's phase, so a launch whose image is building survives a dashboard restart. Verified by the unit tier (578 passed), the postgres tier (36 passed, including a DSQL-style row-privileges login), infra's tests against the branch with its stashed change, and on Union with the test account's dashboard at `b0fdbc5` (the recipe above): a successful build across a restart served both modes with no second build, and a failing build across a restart reached the watching tab. Left: the infra change is still stashed in the infra repo and lands on infra's `main` before the next `upgrade`; a failed build with no page open isn't shown on the next visit, ticket `launch-failure-on-load`; a row whose build run can't be found stays building, ticket `launch-row-unresolvable-run`. No review comments.
