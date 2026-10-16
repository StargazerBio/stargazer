---
title: Notebooks are assets
status: next
priority: normal
created: 2026-10-16
---

A user's notebooks become assets: each is a `.py` file stored in the user's
object store, with an index row carrying `asset=notebook`. Snapshots go, and
so does the dashboard's Workflows section. Workflows and tasks belong in the
SDK, and ideas from notebooks, popular ones especially, move into it by hand
in the repo, as they come up. To the user, the workspace looks as it does now:
every notebook they have is in it. One thing changes: a pod's resources are
picked when it's launched, and no longer declared in the notebook.

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

Resources move to launch because a pod serves more than the notebook it was
launched for. Every one of the user's notebooks is in its `/workspace`, and
any of them can be opened and run there, on the resources and image the pod
was launched with. So a resource figure written in a notebook says nothing
about where that notebook actually runs. What a notebook needs in production
is already declared where it runs: on the `TaskEnvironment` of each task it
calls.

## Decided (2026-10-16)

- **The pod's disk holds the working copy, and the asset holds the saved
  one.** marimo writes every edit to the file on the pod's disk. On its save
  interval and once more at spin-down, the proxy replaces the stored notebook
  asset, just as it saves to the workspace store today. Each replacement gets
  a new CID and deletes the old version, so no history is kept.
- **The workspace looks the same.** At launch the pod still downloads all of
  the user's notebooks side by side into `/workspace`, so marimo's file
  explorer still shows all of them and they can still import each other.
- **Notebooks import each other, and that stays.** The tutorials import each
  other as `stargazer.notebooks.tutorials.*`, so they stay in the image with
  the SDK they teach. They aren't assets.
- **Notebook assets aren't part of the SDK.** No asset class and no catalog
  entry. Only `app/` reads and writes them, through the SDK's generic storage
  client. The SDK could find them with `assemble()`, but that isn't
  documented or relied on.
- **Resources are picked at launch.** The `[tool.stargazer]` resources leave
  notebooks.
- **Private notebooks first.** This ticket covers the user's own notebooks,
  in the object store and the index. Public notebooks are ticket
  `public-notebooks`: a Publish button that works as it does for any asset,
  and the dashboard listing the public tier.
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
  not by clicking in the UI. Not checked: whether beta then runs with alpha's
  PEP 723 packages under `--sandbox`.

## Design

**A notebook asset** is a bare `Asset` with the keyvalues `asset=notebook`,
`title` and `description`. The dashboard lists notebooks from index rows
alone, so it no longer reads every notebook's header when the page loads.

The title also stays in the source's `[tool.stargazer]` header. The index
holds one row per CID, so two notebooks created from the same seed with
identical bytes would collapse into one record. The title is set when the
notebook is created and never changes, so the header and the keyvalue can't
disagree.

The `main_img` setup line stays in the source (Q1). Editing the description
in the gear merges keyvalues and keeps the CID.

**Identity is the filename.** A notebook is `<slug>.py`, which is the index
row's `name` and the `nb-<slug>-<mode>` app name. A user has few notebooks, so
finding one by slug can be a filter over the user's `asset=notebook` rows. No
new index query is needed.

**Storage.** A notebook is stored where every asset is,
`<store root>/users/<owner>/assets/<cid>/<slug>.py`, with its row in the
user's index. `app/workspace_store.py` goes. After that,
`STARGAZER_WORKSPACE_ROOT` is read only to set `STARGAZER_STORE_ROOT`
(`app/onboard.py`, `app/per_notebook.py`, `cli/devbox_dashboard.py`), so set
the store root directly and drop the variable. Check the Litestream replica
path first: it's `<root>/users/<subject>/index`.

**Saving.** Only the proxy replaces a notebook, now that the dashboard never
rewrites a source. A replace stores the new bytes and writes the new row
first. Only then does it delete every other notebook row with that slug, and
the files those rows point to. A save that fails partway leaves the previous
version. An interrupted save leaves two rows: the listing shows the one with
the newest `created_at`, and the next save removes the other.

**The proxy needs the SDK's storage client.** `sg_proxy` runs in the image's
system Python, which has `flyte` but not `stargazer`, so today it writes to
the store with `flyte.storage` directly. Hydrating (listing and fetching) and
saving (CID, store, index row, `_owner`) are exactly what `StorageClient`
does, so install the SDK into the proxy's environment instead of
reimplementing it there. Each kernel runs in its own sandbox venv and won't
see it. Check how much it adds to the image.

**Hydrating.** At launch the pod fetches every notebook asset its owner has
into `/workspace/<slug>.py`, flat, as now. `/snapshots` goes.

**Launch-time resources.** Edit and Run ask for CPU and memory, prefilled with
`DEFAULT_RESOURCES` (1 CPU, 2 Gi), and `/launch` passes them to
`per_notebook_env`. A running notebook shows what it was launched with.
Relaunching with different figures re-serves the pod, the same way a hydrated
Open does today. Nothing is remembered per notebook. A saved suggestion can
come later as keyvalues on the notebook asset if one turns out to be needed.
The gear keeps only the description.

**Dashboard.** Two sections. **Notebooks** holds the user's notebook assets,
with New (from the blank or template seed), Edit and Run, the gear, delete,
and download. **Tutorials** holds the shipped tutorials. Any notebook can
open in Run mode. These go: the Snapshots section and its 📸 button, Copy to
workspace, the Workflows section, and the `public-snapshots` source. The
scRNA notebook moves into Tutorials as the last one (Q3).

## Pieces

- [ ] Notebook operations on the asset layer in `app/`, replacing
      `app/workspace_store.py`: create from a seed, list, get by slug, set
      description, delete, plus the proxy's replace. Write the tests first,
      against a `SqliteIndex` and a temp-dir store:
  - create, then list → the notebook with its title and description
  - create a slug that's already taken → refused
  - replace twice → one row, and the first two versions' files are gone
  - two rows for one slug (an interrupted replace) → the newest is listed, and
    the next replace leaves one row
  - delete → the row and the file are gone
  - a description edit → the CID is unchanged
- [ ] Launch-time resources: `/launch` takes `cpu` and `memory`, and the
      Edit and Run controls ask for them. Remove the `[tool.stargazer]`
      resource parsing and writing (`parse_notebook_resources`, the resource
      half of `with_stargazer_resources`), and the gear's resource fields.
      Test: a launch with `cpu=4, memory=8Gi` → `per_notebook_env` gets them.
      Test: a launch without them → `DEFAULT_RESOURCES`.
- [ ] Dashboard routes on notebook assets: create, settings, delete,
      download, launch. `/launch/status` is unchanged. Remove
      `/workspace/snapshot`, `/snapshot/delete` and `/workspace/copy`, and the
      snapshot and workflow sections in `app/notebooks.py` and
      `app/templates/dashboard.html`. Rewrite the store-backed tests in
      `tests/unit/test_app.py`, and delete the snapshot and copy tests.
- [ ] Proxy hydrate and save through `StorageClient`, with the SDK installed
      in the proxy's environment (the recipe in `app/per_notebook.py`).
      Rewrite the hydrate and save tests in `tests/unit/test_proxy.py`.
- [ ] Move the scRNA notebook into the tutorials, and update its
      `verify-stargazer` feature file.
- [ ] Remove `src/stargazer/notebooks/snapshots/`, `PUBLIC_SNAPSHOTS_DIR` and
      `PublicSnapshot`, `SNAPSHOT_NOTEBOOK_DIR`, `STARGAZER_WORKSPACE_ROOT`,
      and `tests/unit/test_workspace_store.py`.
- [ ] Docs:
  - `docs/architecture/notebook.md`: the types table, the archetypes,
    Promotion Paths (freeze, graduate and copy go, and promotion outside the
    dashboard stays), Notebook Environment (resources are picked at launch),
    Adding Notebooks
  - `docs/architecture/app.md`: topology, request flow, "Saving just works",
    "Resources live in the notebook", "Sharing upstream is a download", the
    Snapshots section, Images
  - `.opencode/reference/architecture/app_internals.md`: the workspace store,
    hydrate and save, creating notebooks and per-notebook resources,
    `main_img`, snapshots, copy, and the route table
  - `docs/architecture/configuration.md`: notebooks in the store layout
  - If a doc is added or removed, update the `zensical.toml` nav. If the
    README mentions snapshots, the Workflows section or per-notebook
    resources, list that drift in the PR and don't edit the README.
- [ ] Verify on Union with the test account (`verify-stargazer`; the closest
      existing feature is `union-main-img`):
  - create a notebook, edit it, and wait one save interval; reopen it after
    the pod scales to zero → the edits are there
  - the index has one row for the notebook, and the store has one file under
    its CID
  - launch with 2 CPU and 4 Gi → the app spec and the pod's cgroup limits
    show them
  - a description edit keeps the CID
  - delete removes the row and the file

  Then add a feature file for saving notebooks, and stop every app the check
  started.

## Open questions

- [ ] **Q1. `main_img` belongs to the pod, as resources do.** A notebook
      opened from the explorer runs on the image the pod was launched with,
      not the one it declares. Keep declaring it in the notebook, with the
      launched notebook's image applying to the whole pod? Or pick it at
      launch too? It's a code expression, which is awkward to pick in a form.
- [ ] **Q2. The asset explorer.** Should the dashboard become an asset
      explorer and notebook launcher in this ticket? Or should the explorer
      be part of `asset-manager-on-index`, which already moves the asset page
      onto the user's index? Merging that page into the dashboard is a small
      step from there.
- [ ] **Q3. Where the scRNA notebook goes.** The default above moves it into
      the tutorials. The alternatives are deleting it (its workflow is in
      the SDK) or publishing it later as a public notebook.
- [ ] **Q4. The save interval.** Each save now means a store PUT, index
      writes through the dashboard, and a delete. Keep 5 s unless measuring a
      busy editing session shows the dashboard feeling it.

## Related tickets

- `public-notebooks`: Publish and the public listing, which come after this
  ticket.
- `bit-for-bit-snapshots`: superseded. Close it as `done`, with an Outcome
  saying so, when this ticket merges.
- `sdk-package`: its step "Decide where the notebooks live" is settled here.
  The tutorials stay in the package, and user notebooks are assets owned by
  the app.
- `asset-manager-on-index`: once the asset page lists the user's index, it
  should leave out `asset=notebook`, since notebooks have their own section.
  It may also become the dashboard's asset explorer (Q2).
- `promote-task-cli`: unchanged.
