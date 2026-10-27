---
title: A running pod's save can overwrite a gear edit
status: review
priority: low
created: 2026-10-21
pr: 88
---

The gear on a workspace tile rewrites a notebook's stored setup block while a running pod of that notebook holds its own copy. If the pod's save later stores its copy, the gear's change is lost. That's inferred from the code, not reproduced (ticket `notebook-environment`).

## Reproduced (2026-10-26, locally)

Through the real modules on a local store root (`app.workspace_store`,
`app.proxy`'s `hydrate_async`, `_seed_from_disk` and `sync_once`, and
`app.notebook_meta.replace_setup_body` as the gear calls it): after a gear
edit, an idle save pass saves nothing and the gear's setup block stays
stored. After one edit to a cell in the pod's copy, the next pass saves the
file and the stored setup block is the pod's old one. The pod saves any file
whose size or mtime changed and never rereads the store, so whatever it
saves overwrites the gear's edit. Not run on Union: marimo rewriting the
file when a cell is edited, which is how edit mode saves (inferred).

## Fix (decided 2026-10-26)

The gear refuses while the notebook has a running pod, in either mode. The
modal says to stop the notebook first, or to edit the setup block in the
notebook itself. `POST /workspace/setup` checks the user's `nb-*` apps the
way `/launch/status` does and answers 409 when the notebook's is up, so a
stale page can't get around it.

Test it: with a running app for the notebook, the save route answers 409 and
the stored notebook is unchanged; with none, the save goes through.

Choices: the check is one `App.get` per mode (the names are known, so no
project listing) and refuses on `is_active()`, a starting pod included. An
app that can't be fetched counts as stopped, as in `/launch/status`. The
409's message shows in the modal's save alert, and the modal's note says the
same up front.

## Verification recipe: The gear refuses while the notebook runs

A workspace notebook's gear won't save while the notebook has a running pod
in either mode; the save names the fix. Once it's stopped, the save goes
through. Driven on the Union tenant as the test account.

### Sub-features

- `gear-409` a save while the notebook runs is refused with the message, and the stored setup block is unchanged.
- `gear-after-stop` a save after Stop goes through and retitles the tile.

### How to get to it (user POV)

Launch a workspace notebook, click its tile's gear, change the description, click Save.

### Driving it

Preconditions: the Union lock held, `.flyte/union.yaml` linked, the console
signed in (built-in browser), `STARGAZER_TARGET=union` and infra's
`tenant.env` exported.

- `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy`, open the dashboard from the console tab with `location.href`.
- Record the stored block: `fetch('/workspace/setup?slug=<slug>')`.
- Replace `window.alert` with a recorder (an alert blocks the pane), click **Run** on the tile, wait until `/launch/status` lists it.
- Open the gear, change `main_description`, click **Save**: the recorded alert is `Save failed: Stop the notebook before changing its setup here, or edit the setup block in the notebook itself.`, the modal stays open, and the stored block equals the recorded one. A direct POST answers `409`. (`gear-409`)
- Click **Stop**, wait until `/launch/status` is empty, repeat the save: no alert, the modal closes, the tile shows the new description and the stored block is the recorded one with the edit. (`gear-after-stop`)
- Put the block back with a POST of the recorded one, then `union_dashboard.py teardown`: `live runs: []`.

### Gotchas

- Edit mode is the same check with the other app name; the unit tests cover both modes, the drive covers run mode.

## Progress

- [x] 409 from `POST /workspace/setup` while an `nb-<slug>-*` app is active, modal note (branch `fix/gear-save-race`)
- [x] Unit tests (both modes refused, stopped app lets the save through)
- [x] Verified on Union 2026-10-26 (run mode): `gear-409`, `gear-after-stop`
