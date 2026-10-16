---
title: Notebooks are assets
status: next
priority: normal
created: 2026-10-16
---

A user's notebooks become assets: each is a `.py` file stored in the user's
object store, with an index row carrying `asset=notebook`. Snapshots go. Each
user has one workspace, and to them it looks as it does now: every notebook
they have is in it. Workflows and tasks belong in the SDK, and ideas from
notebooks, popular ones especially, move into it by hand in the repo, as they
come up.

## Why

The dashboard has four kinds of notebook (tutorials, workflows, workspace,
snapshots), each with its own storage, routes and ways to move between kinds:
a separate workspace store, freeze, copy to workspace, published versus own
snapshots, and a run-only mode. All of that answers "where does this notebook
live and what can I do with it?", and the asset system already answers that
for every other file: a CID, keyvalues, private in the object store, public on
Pinata. Making notebooks assets removes one storage layer and most of the
promotion machinery. It's the same split as ticket `sdk-package`: notebooks and
the app on one side, tasks and workflows in the SDK on the other.

## Decided (2026-10-16)

- **The pod's disk holds the working copy, and the asset holds the saved
  one.** marimo writes every edit to the file on the pod's disk. On its save
  interval and once more at spin-down, the proxy replaces the stored notebook
  asset, just as it saves to the workspace store today. Each replacement gets
  a new CID and deletes the old version, so no history is kept.
- **The workspace looks the same.** At launch the pod still downloads all of
  the user's notebooks side by side into `/workspace`. So marimo's file
  explorer still shows them all, they can still import each other, and the
  SDK's source still isn't in view.
- **Every file in the workspace is saved, not just notebooks.** A file the
  user writes there, from a cell or the terminal, is saved as a plain asset (a
  blob) and comes back at the same path the next time a pod starts. Notebooks
  are the files that also carry `asset=notebook`.
- **A notebook is an asset type like any other:** `Notebook`, in
  `src/stargazer/assets/`.
- **Image and resources stay in the notebook.** This ticket leaves both as
  they are. Making them one declaration is ticket `notebook-environment`.
- **The tutorials and the scRNA notebook leave the SDK and become public
  notebooks.** That happens in ticket `public-notebooks`, which also removes
  the Tutorials and Workflows sections. Until then they ship as they do now.
- **Private notebooks first.** This ticket covers the user's own notebooks,
  in the object store and the index. Public notebooks are ticket
  `public-notebooks`.
- **No migration.** There are no real users yet. The old `notebooks/` and
  `snapshots/` prefixes stay in the bucket, and nothing reads them.
- **Promotion happens outside the dashboard.** Ideas move from notebooks into
  the SDK by hand, in the repo (ticket `promote-task-cli` stays `maybe`), not
  through moves on the dashboard. It may be automated later.

## Measured (2026-10-16)

Measured locally with the image's marimo (0.23.6) and the pod's layout: the
working directory is `/workspace`, and `marimo edit` is started on one file
from there. Neither result has been checked in a pod.

- **The file explorer opens at the working directory.**
  `/api/files/list_files` lists the workspace notebooks even when the launched
  notebook is a tutorial elsewhere. The SDK at `/stargazer` and the snapshots
  in `/snapshots` don't appear at the top level.
- **Another notebook in the folder opens and runs in the same server.** A
  session for `beta.py`, opened in a server launched on `alpha.py`, came up
  with beta's source. The test opened the session over marimo's websocket,
  not by clicking in the UI. So a notebook opened that way runs on the pod
  it was opened in, with that pod's resources and image (see
  `notebook-environment`). Not checked: whether it also gets the launched
  notebook's PEP 723 packages under `--sandbox`.

## Design

**The `Notebook` asset** lives in `src/stargazer/assets/notebook.py`, with
`_asset_key = "notebook"` and the fields `title` and `description`. The
dashboard lists notebooks from index rows alone, so it no longer reads every
notebook's header when the page loads.

The title also stays in the source's `[tool.stargazer]` header. The index
holds one row per CID, so two notebooks created from the same seed with
identical bytes would collapse into one record. The title is set when the
notebook is created and never changes, so the header and the keyvalue can't
disagree.

`description` leaves the header, so editing it in the gear merges keyvalues
and keeps the CID. The header's resources and the `main_img` setup line stay
where they are.

**Identity is the path in the workspace.** Every saved file carries a
`workspace_path` keyvalue, such as `scrna.py` or `data/counts.csv`.

- **Notebooks** are the top-level `.py` files, as they are today. A notebook
  is a `Notebook` with `workspace_path=<slug>.py`, and the slug is also the
  `nb-<slug>-<mode>` app name.
- **Every other file** is a bare `Asset` with only `workspace_path`.
  `specialize()` already returns a bare `Asset` for a record with no
  registered type.
- **Some files aren't saved:** dotfiles, `__pycache__/`, and marimo's own
  `__marimo__/` session caches, which it writes beside each notebook.
- **Lookups:** a user has few files, so finding one by path can be a filter
  over their rows. No new index query is needed.

**Storage.** A notebook is stored where every asset is,
`<store root>/users/<owner>/assets/<cid>/<slug>.py`, with its row in the
user's index. `app/workspace_store.py` goes. After that,
`STARGAZER_WORKSPACE_ROOT` is read only to set `STARGAZER_STORE_ROOT`
(`app/onboard.py`, `app/per_notebook.py`, `cli/devbox_dashboard.py`), so set
the store root directly and drop the variable. Check the Litestream replica
path first: it's `<root>/users/<subject>/index`.

**Replacing a file** works the same way for notebooks and blobs. It stores
the new bytes and writes the new row first. Only then does it delete every
other row with that `workspace_path`, and the files those rows point to. A save that fails partway leaves the previous
version. An interrupted save leaves two rows: the listing shows the one with
the newest `created_at`, and the next save removes the other.

Two things replace a notebook: the proxy when it saves, and the dashboard
when the gear changes resources, which rewrites the header. So the replace
lives in the SDK, beside `Notebook`, because the proxy can't import `app/`.
Once `notebook-environment` moves resources into the notebook's code, the
gear stops writing code, and the proxy is the only caller.

**The proxy needs the SDK's storage client.** `sg_proxy` runs in the image's
system Python, which has `flyte` but not `stargazer`, so today it writes to
the store with `flyte.storage` directly. Hydrating (listing and fetching) and
saving (CID, store, index row, `_owner`) are exactly what `StorageClient`
does, so install the SDK into the proxy's environment instead of
reimplementing it there. Each kernel runs in its own sandbox venv and won't
see it. Check how much it adds to the image.

**Hydrating.** At launch the pod fetches every workspace file its owner has
to `/workspace/<workspace_path>`. Notebooks land flat at the top, as now.
`/snapshots` goes.

**Change detection has to be cheap.** Today each save pass reads and hashes
every file in full (`_digest(path.read_bytes())` in `app/proxy.py`). That's
fine for notebooks, but not for a multi-gigabyte blob every 5 s. Compare size
and modification time first, and hash only the files where either changed.

**Dashboard.** The Workspace section lists the user's notebook assets, with
New (from the blank or template seed), Edit and Run, the gear, delete, and
download. Any notebook can open in Run mode. The Snapshots section and its
📸 button go. Tutorials and Workflows stay until `public-notebooks`. Copy to
workspace stays on the scRNA tile, where it now creates a notebook asset.

## Pieces

- [ ] `Notebook` asset type and its replace. Write the tests first, against a
      `SqliteIndex` and a temp-dir store:
  - it round-trips its keyvalues, and `assemble(asset="notebook")` returns it
    typed
  - replace twice → one row, and the first two versions' files are gone
  - two rows for one slug (an interrupted replace) → the newest is listed, and
    the next replace leaves one row
- [ ] Notebook operations in `app/`, replacing `app/workspace_store.py`:
      create from a seed, list, get by slug, set description, delete. Tests:
  - create, then list → the notebook with its title and description
  - create a slug that's already taken → refused
  - delete → the row and the file are gone
  - a description edit → the CID is unchanged
- [ ] Dashboard routes on notebook assets: create, settings, delete,
      download, launch, and copy from the scRNA notebook. `/launch/status`
      is unchanged. Remove `/workspace/snapshot`, `/snapshot/delete`, the
      snapshot sources of copy and launch, and the Snapshots section in
      `app/templates/dashboard.html`. Rewrite the store-backed tests in
      `tests/unit/test_app.py`, and delete the snapshot tests.
- [ ] Proxy hydrate and save through `StorageClient`, with the SDK installed
      in the proxy's environment (the recipe in `app/per_notebook.py`).
      Rewrite the hydrate and save tests in `tests/unit/test_proxy.py`, and
      add:
  - a CSV written to `data/` → saved as a bare asset with
    `workspace_path=data/counts.csv`, and hydrated back to the same path
  - a file under `__marimo__/` or `__pycache__/`, or a dotfile → not saved
  - an unchanged file whose size and modification time match → not read on
    the next pass
- [ ] Remove `src/stargazer/notebooks/snapshots/`, `PUBLIC_SNAPSHOTS_DIR` and
      `PublicSnapshot`, `SNAPSHOT_NOTEBOOK_DIR`, `STARGAZER_WORKSPACE_ROOT`,
      and `tests/unit/test_workspace_store.py`.
- [ ] Docs:
  - `docs/architecture/notebook.md`: the types table, the archetypes,
    Promotion Paths (freeze goes, and promotion outside the dashboard
    stays), Adding Notebooks
  - `docs/architecture/app.md`: topology, request flow, "Saving just works",
    "Sharing upstream is a download", the Snapshots section
  - `.opencode/reference/architecture/app_internals.md`: the workspace store,
    hydrate and save, creating notebooks, snapshots, copy, and the route
    table
  - `docs/architecture/types.md` and the catalog (`docs/gen_catalog.py`)
  - `docs/architecture/configuration.md`: notebooks in the store layout
  - If a doc is added or removed, update the `zensical.toml` nav. If the
    README mentions snapshots, list that drift in the PR and don't edit the
    README.
- [ ] Verify on Union with the test account (`verify-stargazer`; the closest
      existing feature is `union-main-img`):
  - create a notebook, edit it, and wait one save interval; reopen it after
    the pod scales to zero → the edits are there
  - the index has one row for the notebook, and the store has one file under
    its CID
  - a description edit keeps the CID, and a resource edit replaces it
  - delete removes the row and the file
  - a file written from the terminal into `/workspace/data/` is there after
    the pod scales to zero and is reopened

  Then add a feature file for saving notebooks, and stop every app the check
  started.

## Open questions

- [ ] **Q1. The save interval.** Each save now means a store PUT, index writes
      through the dashboard, and a delete. Keep 5 s unless measuring a busy
      editing session shows the dashboard feeling it.
- [ ] **Q2. Deleting a file in the pod.** Today a deletion in the pod
      doesn't reach the store, because deleting is a dashboard action. With
      arbitrary files, `rm data/old.csv` in the terminal would come back at
      the next launch.

      Proposal: delete the asset when a file disappears, but only one this
      pod hydrated or saved itself. A failed hydrate (which today starts an
      empty workspace and keeps serving) then knows of no files, so it can't
      delete the user's store.

## Related tickets

- `asset-manager-on-index`: the dashboard as asset explorer and notebook
  launcher, which is ahead of this ticket in the queue. Whichever of the two
  lands second makes the browser leave out `asset=notebook`.
- `notebook-environment`: makes image and resources one declaration in the
  notebook.
- `public-notebooks`: Publish, the public listing, and the tutorials and
  scRNA notebook as public notebooks.
- `bit-for-bit-snapshots`: superseded. Close it as `done`, with an Outcome
  saying so, when this ticket merges.
- `sdk-package`: its step "Decide where the notebooks live" is settled. User
  notebooks are assets, and the tutorials and scRNA notebook leave the
  package as public notebooks.
- `promote-task-cli`: unchanged.
