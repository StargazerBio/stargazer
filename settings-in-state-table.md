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

## Verification recipe: Settings as state-table rows

The save interval and the asset explorer's default filter are each kept on their own, so saving one never undoes the other, and a notebook launched afterwards uses the saved interval.

### Sub-features

- `st-fresh`: before any save the account is on the defaults: the Settings modal shows 30 and the explorer opens on Mine and Stargazer, whatever `settings.json` held.
- `st-both`: the interval and the default filter saved at the same moment both read back after a reload.
- `st-reset`: Reset brings back the built-in filter and leaves the interval alone.
- `st-launch`: a notebook launched after a save gets that interval in its pod (`SG_SAVE_INTERVAL_SECONDS`).

### How to get to it (user POV)

- Dashboard header ⚙️ → Settings modal (save interval, the saved default's summary and Reset). The explorer's Save as default.

### Driving it

Preconditions: the `verify-stargazer` Union tenant preconditions; the built-in browser pane signed in to the console as the test account. The test account's state table exists (made for ticket `launch-build-state`).

- **Deploy.** With infra's `tenant.env` exported and `STARGAZER_TARGET=union`, `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy`; open the printed URL from the console page with `location.href`. The footer shows the branch's commit.
- **`st-fresh`.** On the page, `document.querySelector('#settings-modal input[name=save_interval_seconds]').value` is `"30"` and `EXPLORER_DEFAULT.sources` is `["mine","stargazer"]`.
- **`st-both`.** From the page: `await Promise.all([fetch("/settings",{method:"POST",body:new URLSearchParams({save_interval_seconds:"60"})}), fetch("/settings/explorer-default",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sources:["stargazer"],types:["notebook"],keyvalues:{},text:"st-probe"})})]).then(rs=>rs.map(r=>r.status))` is `[200,200]`. Reload: the modal input reads 60 and `EXPLORER_DEFAULT` is the saved filter. Then open ⚙️ and save 45 in the modal: "Saved." shows, and after a reload the filter is still the saved one.
- **`st-reset`.** Click Reset in the modal. Reload: `EXPLORER_DEFAULT` is Mine and Stargazer, the interval still 45.
- **`st-launch`.** Launch a workspace notebook's Run; `App.get(name="nb-<slug>-run", project="u-pryce", domain="development")`'s container env has `SG_SAVE_INTERVAL_SECONDS=45`.
- **Restore** the interval to its pre-test value through the modal.
- **Teardown.** `union_dashboard.py teardown`: `live runs: []`.
