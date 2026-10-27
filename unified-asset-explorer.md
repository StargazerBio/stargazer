---
title: One asset explorer for everything but the workspace
status: doing
priority: high
created: 2026-10-26
blocked_by:
  - dashboard-header-controls
  - workspace-slug-shadows-shipped
---

The Workspace is a blob: the user's own files, saved as they are, so it
keeps its own section on the dashboard. Everything else is an asset and
lives in one explorer: the user's stored assets, public assets, public
notebooks, and the notebooks Stargazer ships (Tutorials and Workflows). The
Workflows, Tutorials and Public notebooks sections go, and their entries are
found, filtered and opened from the explorer like any other asset.

This is the first of three tickets on the explorer. Ticket
`explorer-filter-defaults` gives it real filters and per-user defaults, and
ticket `constellation-graph` redraws its graph.

## Current State

- `app/admin_app.py` `dashboard()` renders Workflows and Tutorials from
  `app/notebooks.py` `by_section()` as tiles (`_tile.html`), each with Edit
  and Run (`POST /launch` with `section`), and Copy to workspace on
  workflows. Tiles poll `/launch/status` to show "Open" and Stop once a pod
  runs.
- Ticket `public-notebooks` (PR #90) adds a Public notebooks section with
  Copy to workspace, and makes the asset browser leave out `asset=notebook`.
- The asset browser (`app/templates/_assets.html`, routes in
  `app/assets.py`) has Public and Private tabs, each a separate listing
  (`GET /assets/list?network=`), in Graph and List views, with a detail card.

## Target State

**One listing, every source.** The explorer loads entries from three
sources and shows them together:

| Source | Entries | Where from |
|---|---|---|
| `mine` | The user's stored assets | The user's index |
| `public` | Public assets and public notebooks | Pinata's public network (cached) |
| `stargazer` | Tutorials and Workflows | The notebooks shipped in the image |

Each entry has the shape the browser already uses, plus its source:

```json
{"cid": "bafk…", "name": "tasks.py", "source": "stargazer",
 "keyvalues": {"asset": "notebook", "category": "tutorial",
               "title": "Tasks", "description": "…", "slug": "tasks"}}
```

A shipped notebook's CID is `compute_cid` of its file, worked out once when
the dashboard starts. `category` is `tutorial` or `workflow`, from
`by_section()`. Public notebooks carry no `category`.

**Source replaces the network tabs.** The Public/Private tabs become a
source control (Mine · Public · Stargazer, several at once). It starts on
Mine and Stargazer, so the tutorials are in front of a new user without the
whole public tier. With public assets off (`STARGAZER_PUBLIC_ASSETS=off`),
Public isn't offered, as the tab isn't now.

**Notebook entries act like their tiles did.** A notebook's detail card
shows its title and description and the actions its tile had: Edit and Run
for shipped notebooks (with the "Open" link and Stop once its pod runs),
Copy to workspace for workflows and public notebooks, and Download source.
In the list view a notebook row shows its title. Uploads still never create
a notebook: the upload form's types leave out `notebook`, and publishing
stays on the workspace tile.

**The Workspace section stays as it is**, including Create, the gear,
Publish and Unpublish.

## Implementation Plan

### Phase 1: The listing

1. `app/assets.py`: `GET /assets/list` takes `source` (repeatable:
   `mine`, `public`, `stargazer`) in place of `network`, and returns the
   union, each entry stamped with `source`. Keyvalue filters apply to every
   source. `mine` needs the owner, as `network=private` does; `public` keeps
   its anonymous read and its cache; `stargazer` is anonymous.
2. `app/notebooks.py`: the shipped notebooks as entries, CIDs computed once
   and cached in the module.
3. The `network` parameter stays on the upload, update and download routes,
   which act on one record's store.
4. Tests in `tests/unit/test_assets_routes.py`: `source=stargazer` lists
   every shipped notebook with `asset=notebook` and its category; `mine` and
   `stargazer` together return both, each with its `source`; `asset=notebook`
   with `source=mine` is empty; anonymous `source=mine` is 401; with public
   off, `source=public` is 503.

### Phase 2: The explorer

1. `_assets.html`: the source control in place of the network tabs; the
   listing fetched for the chosen sources; `source` shown in the list view
   and the detail card. Public records the user owns keep their green mark.
2. The notebook detail card's actions, reusing the tile's launch, status
   polling, Stop and copy code from `dashboard.html`, moved where both can
   use it.
3. `dashboard.html`: the Workflows, Tutorials and Public notebooks sections
   go. `dashboard()` stops passing `tutorials` and `workflows`.
4. Leaving out `asset=notebook` (from ticket `public-notebooks`) is
   reversed for the listing, and kept for the upload form's types.

### Phase 3: Docs and verification

1. `docs/architecture/app.md`: the home page is the Workspace and the
   explorer; the explorer's sources; notebooks as entries. Also
   `.claude/reference/architecture/app_internals.md`, and any mention of the
   Tutorials or Workflows sections in `docs/architecture/notebook.md`,
   `overview.md` and the guides.
2. Verify on the test account's Union dashboard in the built-in browser:
   the default view shows the user's assets and the shipped notebooks; a
   tutorial launches in Edit mode from its detail card, its "Open" link
   works and Stop stops it; Copy to workspace on a workflow makes a
   workspace tile; Public adds public records and public notebooks; a
   private upload still lands in Mine. Tear down after.

## File Changes

| File | Changes |
|---|---|
| `app/assets.py` | `source` on the listing; the union of sources |
| `app/notebooks.py` | Shipped notebooks as entries with CIDs |
| `app/admin_app.py` | `dashboard()` drops the shipped sections |
| `app/templates/_assets.html` | Source control, notebook entries and actions |
| `app/templates/dashboard.html` | The shipped and public notebook sections go |
| `app/templates/_tile.html` | Workspace only |
| `tests/unit/test_assets_routes.py` | The source tests |
| `docs/architecture/app.md`, `app_internals.md` | The explorer |

## Design Decisions

1. **Shipped notebooks are listed, not stored.** They're projected from the
   image when the explorer lists them. Nothing writes them to an index or to
   Pinata, which keeps the 2026-10-17 decision that repo notebooks aren't
   published (ticket `public-notebooks`) and leaves nothing to drift when
   the image changes. Their CID is real, from their bytes, so they are
   addressed like any asset.
2. **Tutorial and workflow become a keyvalue, `category`.** The sections'
   difference survives as something the explorer can filter on.
3. **The default sources are Mine and Stargazer.** The public tier is every
   user's shared records, so it's opt-in, as the Private tab was the default
   before. Ticket `explorer-filter-defaults` lets a user change this.
4. **One listing route.** The explorer asks for the sources it shows and
   gets one list, rather than the page stitching three routes together.

## Open Questions

- [ ] **The SDK's tasks and workflows as entries.** The MCP server's
      registry lists them; they could be `stargazer` entries too, with their
      signatures on the detail card. Left out until someone wants them.

## Choices made in implementation

- No `source` on the listing, or an unknown one, is a 400.
- A shipped notebook's source downloads from the `stargazer` network on the
  download route (`/assets/download/{cid}?network=stargazer`).
- An entry's identity in the page is `source:cid`, since one CID can sit in
  two sources.
- Notebook cards have no metadata editor; a notebook's metadata comes from
  where it's published.
- Copy to workspace on a card only shows when the dashboard has a workspace.
- The launch, status and copy JS lives in `app/static/launch.js`.

## Verification recipe: The unified asset explorer

The dashboard's home page is the Workspace and the explorer. The explorer
lists the user's assets, the public tier and Stargazer's shipped notebooks
together, picked with a Mine · Public · Stargazer control; a notebook's card
launches, copies and downloads it the way its tile did.

### Sub-features

- `ux-default`: on load, Mine and Stargazer are pressed, Public isn't; the
  shipped notebooks (4 tutorials, the scRNA workflow) and the user's assets
  are listed, each with its source. No Workflows, Tutorials or Public
  notebooks section is on the page.
- `ux-launch`: a tutorial's card → Edit launches it; the card shows "Open:
  Edit Mode" and Stop; Open loads the notebook; Stop stops the app.
- `ux-copy`: Copy to workspace on the scRNA workflow's card adds a workspace
  tile.
- `ux-public`: pressing Public adds public records and public notebooks
  (`source=public`).
- `ux-upload`: a private upload lands in Mine.
- `ux-phone`: at 375 px the page has no horizontal scroll
  (`document.documentElement.scrollWidth <= innerWidth`).

### How to get to it (user POV)

Dashboard → Assets (below the Workspace) → the source buttons, the Graph /
List toggle, a node or row → its card.

### Driving it

Preconditions: the `verify-stargazer` Union tenant preconditions; the
built-in browser pane signed in to the console as the test account; the
Union lock held.

- **Deploy.** With infra's `tenant.env` exported, `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy`. Open the printed URL from the console page with `location.href`. Replace `window.alert` with a recorder (`window.alerts=[]; window.alert=m=>alerts.push(m)`) before clicking anything that can fail.
- **Default (`ux-default`).** `[...document.querySelectorAll('#source-tabs button')].map(b=>[b.dataset.source,b.getAttribute('aria-pressed')])` is mine/true, public/false, stargazer/true. Switch to List: five Stargazer rows titled as their tiles were, plus the account's own assets. `document.querySelector('input[name=section][value=tutorials]')` is null until a card is open.
- **Launch (`ux-launch`).** Click the "2. Tasks" row, then Edit on its card: "Open: Edit Mode" and Stop appear; the Open link loads the marimo editor; Stop restores Edit and Run, and `flyte --config .flyte/union.yaml get app nb-tasks-edit -p <project> -d development` shows it stopped.
- **Copy (`ux-copy`).** Click the scRNA-seq row, then Copy to workspace: a "scRNA-seq" tile appears in the Workspace. Delete it after.
- **Public (`ux-public`).** Press Public: rows with source Public appear, including any `notebook` record; `fetch('/assets/list?source=public&asset=notebook')` returns them.
- **Upload (`ux-upload`).** Upload a small file as Private: it's listed under Mine. Note its CID for teardown.
- **Phone (`ux-phone`).** `resize_window` mobile, reload, check `scrollWidth <= innerWidth` and screenshot; then preset desktop.
- **Teardown.** Delete the copied tile; `union_dashboard.py teardown`: `live runs: []`.

### Gotchas

- A failed launch raises a browser alert, which blocks the pane: install
  the alert recorder first.
