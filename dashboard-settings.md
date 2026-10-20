---
title: A Settings section on the dashboard, starting with the save interval
status: backlog
priority: normal
created: 2026-10-18
blocked_by:
  - app-502s-behind-cloudflare
---

The dashboard gets a Settings section for the user's own preferences, and the
workspace save interval is its first setting. Pods read the interval from
`SG_SAVE_INTERVAL_SECONDS`, 5 s when unset, and nothing sets it: the
per-deployment setting `STARGAZER_SAVE_INTERVAL_SECONDS` came out of ticket
`save-whole-workspace` (PR #41) before merge, so that the setting lives here,
with the user.

Blocked by `save-whole-workspace` because the pods' interval and the
workspace store's layout land in that PR. Settings is for the user. The gear
on a notebook tile stays as it is, for that notebook's resources.

## Design

**Stored per user** as `<WORKSPACE_ROOT>/users/<subject>/settings.json`, a
JSON object, beside `workspace/` rather than in it, so pods don't hydrate it
into `/workspace`. It survives the dashboard scaling to zero. A user with no
file gets the default, 5 s.

**Applied at launch.** `/launch` reads the user's settings and passes the
interval to the pod as `SG_SAVE_INTERVAL_SECONDS` in `per_notebook_env`. A
running notebook keeps the interval it started with. The section says so: a
change applies the next time a notebook starts.

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
- [ ] Docs: `docs/architecture/app.md` (the dashboard's sections, and the
      store layout), and `.opencode/reference/architecture/app_internals.md`
      (the route table, the store layout, and Save on an interval).
- [ ] Verify on Union with the test account: set 60 in Settings, launch a
      notebook, and read `SG_SAVE_INTERVAL_SECONDS=60` in the pod's
      terminal. Let the dashboard scale to zero, reopen it, and the setting
      is still 60. Set -1 and get the error. Stop every app the check
      started.

## Related tickets

- `assets-on-dashboard-home` reworks the dashboard's home page, so whichever
  lands second places Settings in the new layout.
