---
title: Dashboard settings move to the per-user state table
status: doing
priority: normal
created: 2026-10-27
---

A user's dashboard settings, the save interval and the filter the asset explorer opens on, are one JSON object in the workspace store (`users/<subject>/settings.json`). Each route that changes one setting reads the whole object, changes its field and writes it all back (`save_settings`, `save_explorer_default`, `reset_explorer_default` in `app/admin_app.py`), so two saves at once from two tabs can undo each other.

Once ticket `launch-build-state` gives each user a state table on their index, each setting is its own row there, written on its own.

## Plan

- [ ] One row per setting: `settings:save_interval_seconds` and `settings:explorer_default` (JSON text). Reading fills in `DEFAULT_SETTINGS` for any row that isn't there.
- [ ] Saving a setting writes its row alone; resetting the default filter deletes its row.
- [ ] Removed: `get_settings`, `put_settings` and `_settings_uri` in `app/workspace_store.py`, and the read-change-write in the three routes. `DEFAULT_SETTINGS` moves to wherever settings are read.
- [ ] The test account's saved settings aren't carried over; it starts on the defaults.
- [ ] Docs: the workspace store and settings parts of `docs/architecture/app.md` and `app_internals.md`, and `app/workspace_store.py`'s docstring.

## Verification

- Tests first: saving the save interval and the default filter at once keeps both; a reset returns the built-in filter and leaves the save interval alone.
- Tenant, test account: save each setting in the header's Settings modal, reload, and both are kept; a notebook launched afterwards saves at the new interval.
