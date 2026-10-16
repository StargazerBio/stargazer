---
title: Notebooks are assets
status: next
priority: normal
created: 2026-10-16
---

A notebook becomes an asset like any other: a `.py` file with keyvalues
(`asset=notebook`), stored in the user's object store, recorded in their index,
and found with `assemble(asset="notebook")`. The dashboard shows one Notebooks
section. Snapshots go, and so does the dashboard's Workflows section. Workflows
and tasks belong in the SDK, and ideas from notebooks, popular ones especially,
move into it by hand in the repo, as they come up.

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
  asset, just as it saves to the workspace store today. Each replacement gets a
  new CID and deletes the old version, so no history is kept.
- **Private notebooks first.** This ticket covers the user's own notebooks, in
  the object store and the index. Public notebooks are ticket
  `public-notebooks`: a Publish button that works as it does for any asset,
  and the dashboard listing the public tier.
- **No migration.** There are no real users yet. The old `notebooks/` and
  `snapshots/` prefixes stay in the bucket, and nothing reads them.
- **Promotion happens outside the dashboard.** Ideas move from notebooks into
  the SDK by hand, in the repo (ticket `promote-task-cli` stays `maybe`), not
  through moves on the dashboard. It may be automated later.

## Design

**The `Notebook` asset** lives in `src/stargazer/assets/notebook.py`, with
`_asset_key = "notebook"` and the fields `title` and `description`. The
dashboard lists notebooks from index rows alone, so it no longer reads every
notebook's header when the page loads. The source keeps what a launch reads
from it: the `[tool.stargazer]` resources and the `main_img` setup line. It
also keeps the title in its header. The index holds one row per CID, so two
notebooks created from the same seed with identical bytes would collapse into
one record. The title is set when the notebook is created and never changes,
so the header and the keyvalue can't disagree. `description` leaves the
header. Editing it in the gear merges keyvalues (`update_metadata`) and keeps
the CID. Editing resources rewrites the source and replaces the asset.

**Identity is the filename.** A notebook is `<slug>.py`, which is the index
row's `name` and the `nb-<slug>-<mode>` app name. A user has few notebooks, so
finding one by slug can be a filter over `assemble(asset="notebook")`. No new
index query is needed.

**Storage.** A notebook is stored where every asset is,
`<store root>/users/<owner>/assets/<cid>/<slug>.py`, with its row in the
user's index. `app/workspace_store.py` goes. After that,
`STARGAZER_WORKSPACE_ROOT` is read only to set `STARGAZER_STORE_ROOT`
(`app/onboard.py`, `app/per_notebook.py`, `cli/devbox_dashboard.py`), so set
the store root directly and drop the variable. Check the Litestream replica
path first: it's `<root>/users/<subject>/index`.

**Replacing a notebook** stores the new bytes and writes the new row first.
Only then does it delete every other notebook row with that slug, and the
files those rows point to. A save that fails partway leaves the previous
version. An interrupted save leaves two rows: the listing shows the one with
the newest `created_at`, and the next save removes the other. The replace
lives in the SDK, beside the `Notebook` type, because both the dashboard and
the proxy call it and the proxy can't import `app/`.

**The proxy needs the SDK.** `sg_proxy` runs in the image's system Python,
which has `flyte` but not `stargazer`, so today it writes to the store with
`flyte.storage` directly. Hydrating (listing and fetching) and saving (CID,
store, index row, `_owner`) are exactly what `StorageClient` does, so install
the SDK into the proxy's environment instead of reimplementing it there. Each
kernel runs in its own sandbox venv and won't see it. Check how much it adds
to the image.

**Hydrating.** At launch the pod fetches every notebook asset its owner has
into `/workspace/<slug>.py`, flat, as now. Keeping them side by side is what
lets a user's notebooks import each other (see Q1). `/snapshots` goes.

**Dashboard.** One Notebooks section holds the user's notebook assets, with
New (from the blank or template seed), Edit and Run, the gear, delete, and
download. Any notebook can open in Run mode. These go: the Snapshots section
and its 📸 button, Copy to workspace, the Workflows section, and the
`public-snapshots` source. What happens to the tutorials and the scRNA
notebook is Q1.

## Pieces

- [ ] `Notebook` asset type, with a test that it round-trips its keyvalues and
      that `assemble(asset="notebook")` returns it typed.
- [ ] Notebook operations on the asset layer, replacing
      `app/workspace_store.py`: create from a seed, list, get by slug,
      replace, set description, delete. Write the tests first, against a
      `SqliteIndex` and a temp-dir store:
  - create, then list → the notebook with its title and description
  - create a slug that's already taken → refused
  - replace twice → one row, and the first two versions' files are gone
  - two rows for one slug (an interrupted replace) → the newest is listed, and
    the next replace leaves one row
  - delete → the row and the file are gone
  - a description edit → the CID is unchanged
- [ ] Dashboard routes on notebook assets: create, settings, delete,
      download, launch. `/launch/status` is unchanged. Remove
      `/workspace/snapshot`, `/snapshot/delete` and `/workspace/copy`, and the
      snapshot and workflow sections in `app/notebooks.py` and
      `app/templates/dashboard.html`. Rewrite the store-backed tests in
      `tests/unit/test_app.py`, and delete the snapshot and copy tests.
- [ ] Proxy hydrate and save through the SDK, with the SDK installed in the
      proxy's environment (the recipe in `app/per_notebook.py`). Rewrite the
      hydrate and save tests in `tests/unit/test_proxy.py`.
- [ ] Remove `src/stargazer/notebooks/snapshots/`, `PUBLIC_SNAPSHOTS_DIR` and
      `PublicSnapshot`, `SNAPSHOT_NOTEBOOK_DIR`, `STARGAZER_WORKSPACE_ROOT`,
      and `tests/unit/test_workspace_store.py`.
- [ ] Docs:
  - `docs/architecture/notebook.md`: the types table, the archetypes,
    Promotion Paths (freeze, graduate and copy go, and promotion outside the
    dashboard stays), Adding Notebooks
  - `docs/architecture/app.md`: topology, request flow, "Saving just works",
    "Sharing upstream is a download", the Snapshots section, Images
  - `.opencode/reference/architecture/app_internals.md`: the workspace store,
    hydrate and save, creating notebooks, `main_img`, snapshots, copy, and the
    route table
  - `docs/architecture/types.md` and the catalog (`docs/gen_catalog.py`)
  - `docs/architecture/configuration.md`: notebooks in the store layout
  - If a doc is added or removed, update the `zensical.toml` nav. If the
    README mentions snapshots or the Workflows section, list that drift in the
    PR and don't edit the README.
- [ ] Verify on Union with the test account (`verify-stargazer`; the closest
      existing feature is `union-main-img`):
  - create a notebook, edit it, and wait one save interval; reopen it after
    the pod scales to zero → the edits are there
  - the index has one row for the notebook, and the store has one file under
    its CID
  - a description edit keeps the CID
  - delete removes the row and the file
  - a task run from the notebook finds it with `assemble(asset="notebook")`

  Then add a feature file for saving notebooks, and stop every app the check
  started.

## Open questions

- [ ] **Q1. Interop between notebooks, and where the tutorials and the scRNA
      notebook go.** Still to be discussed (2026-10-16). Facts so far:
  - The tutorials import each other as `stargazer.notebooks.tutorials.*`
    through the image's editable SDK. Tasks and Workflows import the Assets
    tutorial's `SampleSheet`, and Execution imports the Workflows tutorial's
    workflow. So the tutorials have to ship with the SDK version they teach.
  - A user's notebooks sit side by side in `/workspace`, so they can import
    each other as plain modules. Inferred: marimo puts the notebook's
    directory on `sys.path`. Not checked in a pod.
  - A notebook asset fetched on its own has neither of these.
- [ ] **Q2. The save interval.** Each save now means a store PUT, index writes
      through the dashboard, and a delete. Keep 5 s unless measuring a busy
      editing session shows the dashboard feeling it.

## Related tickets

- `public-notebooks`: Publish and the public listing, which come after this
  ticket.
- `bit-for-bit-snapshots`: superseded. Close it as `done`, with an Outcome
  saying so, when this ticket merges.
- `sdk-package`: its step "Decide where the notebooks live" is Q1.
- `asset-manager-on-index`: once the asset page lists the user's index, it
  should leave out `asset=notebook`, since notebooks have their own section.
- `promote-task-cli`: unchanged.
