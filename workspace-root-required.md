---
title: A dashboard deploy needs a workspace root
status: backlog
priority: normal
created: 2026-10-27
blocked_by:
  - settings-in-state-table
---

Every real deploy already has a workspace root: infra's `stargazer-users` refuses on Union without `STARGAZER_WORKSPACE_ROOT`, and `devbox/dashboard.py` sets it. The app still handles a dashboard without one at every store-backed route: `_store_ready()` and the 503 in `_workspace_guard` in `app/admin_app.py` (24 references across `app/`), the template's not-configured state, and the conditionals around `STARGAZER_WORKSPACE_ROOT` and `STARGAZER_STORE_ROOT` in `app_env` and `deploy_dashboard`. PR #78 did the same for the index: `deploy_dashboard` refuses without one, and the fallback went.

## Plan

- [ ] `deploy_dashboard` refuses when `config.WORKSPACE_ROOT` is empty, as it refuses with no index.
- [ ] A bare local `uvicorn` run gets a local directory as its workspace root by default, so it still saves notebooks.
- [ ] Removed: `_store_ready`, the 503 branch of `_workspace_guard` (its slug check stays), the template's `workspace_configured` state, and the conditionals that only exist for a missing root.
- [ ] Infra: `main()`'s own check for the workspace root can go, since the deploy refuses itself.
- [ ] Docs: `docs/architecture/app.md`, `app_internals.md` (Deploy Settings), `configuration.md`.

## Verification

- Tests first: a deploy with no workspace root is refused with nothing served (fails before the change). The unit tier passes with the 503 tests removed.
- Devbox: `devbox/dashboard.py` deploys and a notebook is created, launched and saved.
