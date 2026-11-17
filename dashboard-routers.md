---
title: dashboard-routers
status: done
priority: low
created: 2026-11-16
pr: 34
---

Infra's `app/admin_app.py` is 1,578 lines (2026-11-16): the app and its environment, the workspace routes (create, copy, GitHub, setup, delete, download), publishing, settings and the explorer's default filter, and the launch state machine. `app/assets.py` already shows the shape to follow: an `APIRouter` in its own module, included by the app.

## Plan

In the infra repo, behavior unchanged, one router per module:

- [x] `app/workspace.py`: the `/workspace/*` routes and their tile helpers.
- [x] `app/launch.py`: `/launch`, `/launch/status`, `/stop` and the build-settling helpers. If ticket [[header-declared-pod]] goes ahead, do it first: most of this module goes with it.
- [x] `app/settings.py`: settings and the explorer default.
- [x] `admin_app.py` keeps the app, its environment, the dashboard page and health.
- [x] `docs/architecture/app.md` and `.claude/reference/architecture/app_internals.md`'s route table name the new modules.

Verify with the `verify-dashboard` skill on the devbox: every route in the table still answers.

`pr: 34` is infra's PR (StargazerBio/infra#34), not stargazer's. The header-declared-pod ticket is `maybe`, so the launch module was split as planned. The split also added `app/route_helpers.py` (`_failed`, `_workspace_guard`, `_notebook_slug`, `_get_app`, `_delete_app`): workspace and launch both need them, and putting them in either module would have made an import cycle. Imports run `workspace` → `launch` → `settings` → `route_helpers`.

## Evidence

- Route table (method, path, name, response class/model, status, params, dependencies) dumped from `asgi_app.routes`, included routers walked, before and after: 27 rows, identical (measured).
- Unit tier 388 passed before and after; all 70 top-level definitions moved verbatim (AST comparison against `main`) (measured).
- Every test patch takes effect: bypassing each patched name at its call site fails tests. `_serve` fails 1 test, as it does on `main` (measured).
- Devbox: this branch deployed, and every route family was driven with curl (page, health, static, assets list, workspace create/setup/download/copy/publish 503/delete/cleanup, settings and the explorer default, launch of a tutorial and of a workspace notebook, status, stop). The dashboard was stopped afterwards (measured).

**Union tenant (measured, 2026-11-16):** the branch deployed as the test account's dashboard (image built on Union in 1:53). Signed in through the console's GitHub login, the page rendered its Workspace and Assets sections, and `fetch` from the page answered on every route family: `/health` 200; `/assets/schema`, `/assets/list` (mine, featured) 200; `/settings/explorer-default` DELETE then POST of the same filter 200, a bad filter 400; `/workspace/create` 200, `/workspace/setup` and `/workspace/download` 200, `/workspace/copy` of a tutorial 200 and from `public` 400; `/launch` (run) 202, `/launch/status` listed the notebook running once its app was up, and its URL served the marimo page; `/stop` 200 and the status emptied; `/workspace/delete` 200 for both test notebooks; `/workspace/cleanup` 200. Teardown: `stopped: [dashboard]`, `live runs: []`.

## Verification recipe

From the infra worktree: dump `asgi_app.routes` (walk `original_router` on included routers) on `main` and on the branch, and diff. Run `uv run pytest`. Then `uv run python devbox/dashboard.py` and curl each route in the app_internals route table.

## Outcome

Shipped in infra PR 34 (merged 2026-11-17, `b728bcd`): the dashboard's routes split into `app/workspace.py`, `app/launch.py`, `app/settings.py` and `app/route_helpers.py`, behavior unchanged. Verified by an identical route-table dump before and after, the unit tier, and every route family driven on the devbox and on the tenant as the test account (Evidence above). Nothing left; the PR had no review comments.

Related: [[board]], [[header-declared-pod]].
