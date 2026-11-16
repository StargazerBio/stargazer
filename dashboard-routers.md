---
title: dashboard-routers
status: doing
priority: low
created: 2026-11-16
---

Infra's `app/admin_app.py` is 1,578 lines (2026-11-16): the app and its environment, the workspace routes (create, copy, GitHub, setup, delete, download), publishing, settings and the explorer's default filter, and the launch state machine. `app/assets.py` already shows the shape to follow: an `APIRouter` in its own module, included by the app.

## Plan

In the infra repo, behavior unchanged, one router per module:

- [ ] `app/workspace.py`: the `/workspace/*` routes and their tile helpers.
- [ ] `app/launch.py`: `/launch`, `/launch/status`, `/stop` and the build-settling helpers. If ticket [[header-declared-pod]] goes ahead, do it first: most of this module goes with it.
- [ ] `app/settings.py`: settings and the explorer default.
- [ ] `admin_app.py` keeps the app, its environment, the dashboard page and health.
- [ ] `docs/architecture/app.md` and `.claude/reference/architecture/app_internals.md`'s route table name the new modules.

Verify with the `verify-dashboard` skill on the devbox: every route in the table still answers.

Related: [[board]], [[header-declared-pod]].
