---
title: workspace-root-required
status: done
priority: normal
created: 2026-10-27
pr: 9
---

Every real deploy already has a workspace root: infra's `stargazer-users` refuses on Union without `STARGAZER_WORKSPACE_ROOT`, and `devbox/dashboard.py` sets it. The app still handles a dashboard without one at every store-backed route: `_store_ready()` and the 503 in `_workspace_guard` in `app/admin_app.py` (24 references across `app/`), the template's not-configured state, and the conditionals around `STARGAZER_WORKSPACE_ROOT` and `STARGAZER_STORE_ROOT` in `app_env` and `deploy_dashboard`. PR #78 did the same for the index: `deploy_dashboard` refuses without one, and the fallback went.

## Plan

- [x] `deploy_dashboard` refuses when `config.WORKSPACE_ROOT` is empty, as it refuses with no index.
- [x] A bare local `uvicorn` run gets a local directory as its workspace root by default, so it still saves notebooks.
- [x] Removed: `_store_ready`, the 503 branch of `_workspace_guard` (its slug check stays), the template's `workspace_configured` state, and the conditionals that only exist for a missing root.
- [x] Infra: `main()`'s own check for the workspace root can go, since the deploy refuses itself.
- [x] Docs: `docs/architecture/app.md`, `app_internals.md` (Deploy Settings); Stargazer's `configuration.md` had nothing to change.

## Verification

- Tests first: a deploy with no workspace root is refused with nothing served (fails before the change). The unit tier passes with the 503 tests removed.
- Devbox: `devbox/dashboard.py` deploys and a notebook is created, launched and saved.

In review as StargazerBio/infra#9. A bare local run's root is `~/.stargazer/store`, the SDK's local store directory, which the deploy refuses.

## Outcome

Shipped in StargazerBio/infra#9 (merge `744d8fa`): `deploy_dashboard` refuses without a workspace root and bakes it into the dashboard, a bare local run keeps notebooks in `~/.stargazer/store`, and the 503 path, `_store_ready` and the template's not-configured state are gone, along with onboarding's own check. Verified with a bare local run before and after, on the devbox (create, launch, save) and on the tenant (the root in the app spec, create and delete). Nothing left; no follow-ups were left on the PR.

Related: [[settings-in-state-table]].
