---
title: Dashboard settings move to the per-user state table
status: done
priority: normal
created: 2026-10-27
pr: 101
---

A user's dashboard settings, the save interval and the filter the asset explorer opens on, are one JSON object in the workspace store (`users/<subject>/settings.json`). Each route that changes one setting reads the whole object, changes its field and writes it all back (`save_settings`, `save_explorer_default`, `reset_explorer_default` in `app/admin_app.py`), so two saves at once from two tabs can undo each other.

Once ticket `launch-build-state` gives each user a state table on their index, each setting is its own row there, written on its own.

## Plan

- [x] One row per setting: `settings:save_interval_seconds` and `settings:explorer_default` (JSON text). Reading fills in `DEFAULT_SETTINGS` for any row that isn't there.
- [x] Saving a setting writes its row alone; resetting the default filter deletes its row.
- [x] Removed: `get_settings`, `put_settings` and `_settings_uri` in `app/workspace_store.py`, and the read-change-write in the three routes. `DEFAULT_SETTINGS` moves to wherever settings are read.
- [x] The test account's saved settings aren't carried over; it starts on the defaults.
- [x] Docs: the workspace store and settings parts of `docs/architecture/app.md` and `app_internals.md`, and `app/workspace_store.py`'s docstring.

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

### Gotchas

- Right after the deploy, Knative served the previous revision for about 20 s (footer `356e514`, interval 5 from the old `settings.json`). Check the footer reads the branch's commit before taking any reading.
- A page loaded before a `fetch`-driven save still shows the old values in the modal; reload before driving the modal.
- A launch on a new release builds the notebook's image first (a 202 and a build run), which takes several minutes. The pod is served on the first `/launch/status` poll after the build succeeds.

### Evidence (2026-10-27, commit 755aaba, `u-pryce`)

- `st-fresh`: footer `755aaba`; the modal input reads `30` and `EXPLORER_DEFAULT` is Mine and Stargazer with nothing else, although the old `settings.json` held 5. Measured.
- `st-both`: the two parallel POSTs answered `[200, 200]`; a fresh `/` read back interval `60` and the filter `{sources: [stargazer], types: [notebook], text: "st-probe"}`. Then 45 saved in the modal showed "Saved. Notebooks you start from now on use it."; a fresh `/` read back 45 with the same filter. Measured.
- `st-reset`: Reset showed "Reset. The explorer opens on it from your next visit."; a fresh `/` read back Mine and Stargazer, with the interval still 45. Measured.
- `st-launch`: Run on `key-1022` answered 202 with build run `ud24q9z8nr8ljps22ngx` (SUCCEEDED). `nb-key-1022-run` served, and its container env has `SG_SAVE_INTERVAL_SECONDS = 45`. Measured.
- Restored the interval to 5, the account's value before the test. Teardown stopped `nb-key-1022-run` and `dashboard`; `live runs: []`; all 10 apps in `u-pryce` inactive. Measured.

## Outcome

Shipped in PR #101 (merge `336601c`). Each dashboard setting is its own `settings:<name>` row in the owner's state table: a save writes its row alone, Reset deletes the filter's row, and a missing row reads as its default. The settings code is gone from the workspace store. Verified by the unit tier (575 passed). The new concurrent-save test failed before the change. On Union, the test account `u-pryce` at `755aaba` passed the recipe above. Saved settings weren't carried over, so every user starts on the defaults after the next `upgrade`, and the old `settings.json` objects stay in the bucket, unread. No review comments. Ticket `workspace-root-required` is unblocked.

