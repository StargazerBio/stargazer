---
title: A Settings section on the dashboard, starting with the save interval
status: backlog
priority: normal
created: 2026-10-18
blocked_by:
  - save-whole-workspace
---

The dashboard gets a Settings section for the user's own preferences, and the
workspace save interval moves into it as the first setting. Today the
interval is `STARGAZER_SAVE_INTERVAL_SECONDS`, set when the dashboard is
deployed (ticket `save-whole-workspace`, PR #41). Each user has their own
dashboard, so it's already per user, but only whoever deploys the dashboard
can change it. After this, the user changes it on the dashboard.

Blocked by `save-whole-workspace` because the setting it moves lands in that
PR. Settings is for the user. The gear on a notebook tile stays as it is, for
that notebook's resources.

## Design

**Stored per user** as `<WORKSPACE_ROOT>/users/<subject>/settings.json`, a
JSON object, beside `workspace/` rather than in it, so pods don't hydrate it
into `/workspace`. It survives the dashboard scaling to zero. A user with no
file gets the default, 5 s.

**The deployment setting goes.** `STARGAZER_SAVE_INTERVAL_SECONDS` leaves
`app/config.py`, `admin_app.py`'s env and the deployer settings in
`app_internals.md`. The 5 s default lives in code.

**Applied at launch.** `/launch` reads the user's settings and passes the
interval to the pod as `SG_SAVE_INTERVAL_SECONDS`, as it passes the
deployment value today. A running notebook keeps the interval it started
with. The section says so: a change applies the next time a notebook starts.

**The control.** A number of seconds, 0 or more, checked by the dashboard
when it's saved. The text, in product terms: the workspace saves every N
seconds and when the notebook stops; 0 saves only when the notebook stops,
and work since the last save is lost if the notebook stops unexpectedly.

## Pieces

- [ ] `app/workspace_store.py`: read and write `settings.json`. Tests: no
      file → the default interval; a written 60 → read back as 60.
- [ ] Dashboard: a Settings section and a route that saves it. Tests in
      `tests/unit/test_app.py`: saving 60 → the next launch's pod env carries
      `SG_SAVE_INTERVAL_SECONDS=60`; saving -1 or a non-number → refused, and
      the stored value is unchanged.
- [ ] Remove `STARGAZER_SAVE_INTERVAL_SECONDS`: `app/config.py`, the dashboard's
      env in `admin_app.py`, and `test_pod_env_carries_the_save_interval` in
      `tests/unit/test_per_notebook.py`, which moves to the settings.
- [ ] Docs: `docs/architecture/app.md` (the dashboard's sections, and the
      store layout), and `.opencode/reference/architecture/app_internals.md`
      (the route table, the store layout, and the deployer settings table).
- [ ] Verify on Union with the test account: set 60 in Settings, launch a
      notebook, and read `SG_SAVE_INTERVAL_SECONDS=60` in the pod (the
      `union-workspace-save` feature drives the pod's terminal). Let the
      dashboard scale to zero, reopen it, and the setting is still 60. Set
      -1 and get the error. Stop every app the check started.

## Related tickets

- `assets-on-dashboard-home` reworks the dashboard's home page, so whichever
  lands second places Settings in the new layout.
