---
title: The workspace saves every file, and snapshots go
status: review
priority: normal
created: 2026-10-16
pr: 41
---

Each user has one workspace, a folder, and every file in it is saved, with
notebooks treated like any other file. Snapshots go. A notebook becomes an
asset only when it's published (ticket `public-notebooks`). To the user, the
workspace looks as it does now. Workflows and tasks belong in the SDK, and
ideas from notebooks, popular ones especially, move into it by hand in the
repo, as they come up.

## Why

The dashboard has four kinds of notebook (tutorials, workflows, workspace,
snapshots), each with its own storage, routes and ways to move between kinds:
freeze, copy to workspace, published versus own snapshots, and a run-only
mode. Most of that is promotion machinery, and it goes. A notebook is either
a file in someone's workspace or, once published, an asset like any other.
Keeping work in progress out of the asset system means no new CID and index
row on every save. It's the same split as ticket `sdk-package`: notebooks and
the app on one side, tasks and workflows in the SDK on the other.

## Decided

2026-10-16:

- **Snapshots go.** Each user has one workspace.
- **No migration.** There are no real users yet. The old `snapshots/` prefix
  stays in the bucket, and nothing reads it.
- **Image and resources stay in the notebook.** This ticket leaves both as
  they are. Making them one declaration is ticket `notebook-environment`.
- **The tutorials and the scRNA notebook leave the SDK and become public
  notebooks**, in ticket `public-notebooks`, which also removes the Tutorials
  and Workflows sections. Until then they ship as they do now. (Changed
  2026-10-17, below.)
- **Promotion happens outside the dashboard.** Ideas move from notebooks into
  the SDK by hand, in the repo (ticket `promote-task-cli` stays `maybe`). It
  may be automated later.

2026-10-17:

- **Notebooks are saved like any other file in the workspace**, and they
  become assets on Publish. That replaces the 2026-10-16 plan to store every
  notebook as an asset: no `Notebook` type in this ticket, no replace, no
  index rows for work in progress, and no second save loop.
- **Every file is saved**, not only top-level `.py` files as now.
- **The pod's disk is the working copy for normal saves.**
- **The save interval is configurable** (Q1).
- **A file over 100 MB isn't saved.** The user is told, and pointed to
  uploading it as an asset instead.
- **The tutorials stay in the SDK, and the scRNA notebook moves to a
  top-level `notebooks/` folder in the repo** (ticket `top-level-notebooks`),
  replacing the 2026-10-16 plan to publish them. Notebooks in the repo aren't
  published, since GitHub already makes them public.

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
  with beta's source. Ticket `notebook-environment` decides what to do about
  it.

## Design

**What's saved.** Every file under `/workspace`, at its path, one object per
file, under `<WORKSPACE_ROOT>/users/<subject>/workspace/`. Today that prefix
is `notebooks/`. It skips dotfiles, `__pycache__/`, and marimo's
`__marimo__/` session caches. A notebook is still a top-level `.py` file, and
the dashboard's Workspace section lists those as it does now.

**Files over 100 MB.** The proxy doesn't save them. The file stays on the
pod's disk while the pod runs, and is gone once it stops. The user's code or
terminal wrote the file, and the proxy finds it later, on a save pass, so
there's no call of ours to raise an error in. The error is a notice in the
notebook's page instead. The proxy already splices a terminal overlay into
every marimo page, so a banner goes in the same way. It polls a new
`/__sg__/save-status` endpoint, which lists the files the last pass skipped
for size. The banner reads, for example: "`data/big.h5ad` (2.3 GB) is over
100 MB, so it isn't saved with your workspace and will be gone when this
notebook stops. To keep it, store it as an asset from a cell, then delete
it from the workspace:" followed by a snippet to copy. The pod's log gets a
line too.

**Keeping a big file as an asset happens in the notebook** (decided
2026-10-17). The file is already on the pod, so the pod uploads it straight
to the user's store, with no size limit. Going through the asset page would
mean downloading it to the user's machine and uploading it again. Workspace
notebooks already have the SDK (the seeds' PEP 723 header), so the snippet
is the SDK's own calls, the same ones the MCP `upload_file` tool makes, and
no new function:

```python
from pathlib import Path
from stargazer.assets import build_asset
from stargazer.utils.storage import default_client

await default_client.upload(build_asset({"asset": "counts"}), Path("data/big.h5ad"))
```

The banner fills in the path. The docs site isn't hosted, so the banner
carries the snippet itself, rather than a link.

With the cap, a file the proxy reads is at most 100 MB, so it keeps reading
whole files and uploading from memory. It still compares size and
modification time before reading a file: `sync_once` in `app/proxy.py` reads
and hashes every file on every pass (`_digest(path.read_bytes())`), and a few
large files would make each pass read hundreds of megabytes.

**Deletions.** Today a deleted file isn't deleted from the store (notebooks
are deleted from the dashboard), so a file deleted in the terminal would come
back at the next launch. A save also deletes the stored copy of a file that's
gone from `/workspace`, but only for files this pod hydrated or saved. If the
hydrate fails, the pod starts with an empty workspace (logged, not fatal), and
a plain mirror would then wipe the store.

**Hydrating.** At launch the pod downloads every object under the prefix to
its path under `/workspace`. `/snapshots` goes.

**When it saves.** On an interval, and once more at scale-down. The interval
is `SG_SAVE_INTERVAL_SECONDS` on the pod, which the dashboard sets at launch
from its own `STARGAZER_SAVE_INTERVAL_SECONDS`. The default is 5 s, as now,
and 0 turns the interval off, so the pod saves only at scale-down. It's set
per deployment, not per user or notebook. A pass writes only the files that
changed.

The proxy already saves at scale-down: on Knative's SIGTERM, the proxy's
FastAPI shutdown hook runs a last pass. A long interval, or 0, leans on it.
What's known:

- The signal path is fragile and was broken once. Flyte's `fserve` is PID 1
  and forwards SIGTERM to its one direct child only, so the launch chain
  `exec`s down to uvicorn. Uvicorn waits for open connections before running
  the shutdown hook, and the proxy's connection to marimo never closes, so
  without `--timeout-graceful-shutdown 15` the save never ran (measured,
  recorded in `app/launch-notebook.sh`).
- The pod gets 300 s between SIGTERM and SIGKILL. That's what our comments
  say, with no source recorded. The EKS audit log has the pod spec.
- The save at scale-down has never been checked on its own on Union. The
  2026-10-06 tenant run (plan 25) showed edits survive scale-to-zero, but the
  5 s save had already stored them.
- Nothing runs when the pod dies without SIGTERM: the node is lost, the
  kubelet evicts it with no grace (inferred: as for a pod over its
  ephemeral-storage limit, which matters once data files are saved), or the
  proxy process crashes. Then everything not yet saved is lost.
- Whatever hasn't been saved has to upload within the grace period.

**Dashboard.** The Snapshots section and its 📸 button go. Everything else in
the Workspace section stays as it is: New, Edit and Run, the gear, delete and
download. Download is still how a notebook is shared, until Publish.

## Pieces

- [x] Prove the save at scale-down on Union, on its own: deploy with the
      interval at 0, so the save at SIGTERM is the only one, write files in
      a running pod, check the store doesn't have them, stop the pod, and
      check they're in the next pod (below). Not done: reading the pod's
      `terminationGracePeriodSeconds` from the EKS audit log, since the
      read-only AWS session had expired.
- [x] Proxy: save and hydrate every file, with the new prefix, the skips,
      the size and modification-time check, deletions, the 100 MB cap, and
      the interval from `SG_SAVE_INTERVAL_SECONDS`. Tests in
      `tests/unit/test_proxy.py`:
  - a CSV written to `data/` → saved at `workspace/data/counts.csv`, and
    hydrated back to `/workspace/data/counts.csv`
  - a file under `__marimo__/` or `__pycache__/`, or a dotfile → not saved
  - an unchanged file whose size and modification time match → not read on
    the next pass
  - a hydrated file deleted from `/workspace` → deleted from the store at
    the next save
  - a store object the pod never hydrated (the hydrate failed) → kept
  - a file one byte over 100 MB (sparse, so the test writes no data) → not
    in the store, and `/__sg__/save-status` lists its path and size
  - with the interval at 0, a file written while the proxy serves → not in
    the store until shutdown, then stored
- [x] The banner: spliced into marimo's pages beside the terminal overlay,
      polling `/__sg__/save-status`, with the upload snippet. A test: a
      proxied HTML page contains it. Run the snippet once in a workspace
      notebook on a file over 100 MB, against an isolated store, and check
      the index row and the stored bytes.
- [x] Dashboard: `STARGAZER_SAVE_INTERVAL_SECONDS` in `app/config.py`, passed
      to each pod as `SG_SAVE_INTERVAL_SECONDS` in `per_notebook_env`. A
      test: set to 60 → the built environment carries `60`.
- [x] `app/workspace_store.py`: the `workspace/` prefix. A test: a nested
      `lib/helpers.py` and `data/counts.csv` under the prefix → not listed as
      notebooks.
- [x] Remove snapshots: `/workspace/snapshot`, `/snapshot/delete`, the
      snapshot sources of copy and launch, the Snapshots section in
      `app/templates/dashboard.html`, `src/stargazer/notebooks/snapshots/`,
      `PUBLIC_SNAPSHOTS_DIR` and `PublicSnapshot`, `SNAPSHOT_NOTEBOOK_DIR`, the
      `snapshots_uri` layout, and the snapshot tests in
      `tests/unit/test_app.py`. The two routes get a 404 test, as plan 25's
      removed routes have.
- [x] Docs. `STARGAZER_SAVE_INTERVAL_SECONDS` went into the deployer settings
      in `app_internals.md`, where the others are, not `configuration.md`.
      No user guide covers the hosted workspace, so the 100 MB limit is in
      the dashboard's Workspace section text instead.
  - `docs/architecture/notebook.md`: the types table, the archetypes,
    Promotion Paths (freeze goes, and promotion outside the dashboard
    stays)
  - `docs/architecture/app.md`: topology, "Saving just works", the Snapshots
    section
  - `.opencode/reference/architecture/app_internals.md`: Pod Hydrate & Save,
    snapshots, copy, and the route table
  - `docs/architecture/configuration.md`: `STARGAZER_SAVE_INTERVAL_SECONDS`
  - the user guides: what's saved, and the 100 MB limit, in product terms
  - If a doc is added or removed, update the `zensical.toml` nav. If the
    README mentions snapshots, list that drift in the PR and don't edit the
    README.
- [x] Verify on Union with the test account (`verify-stargazer`; the closest
      existing feature is `union-main-img`):
  - edit a notebook and write `data/counts.csv` from the terminal, let the
    pod scale to zero, reopen → both are there
  - delete a file from the terminal, scale to zero, reopen → it stays
    deleted
  - write a 150 MB file from the terminal → the banner names it within one
    interval, and it isn't in the store. Run the banner's snippet in a cell
    → the file is an asset, and `assemble()` finds it from a task pod
  - the dashboard has no Snapshots section

  Then add a feature file for saving the workspace, and stop every app the
  check started.

## Verified on Union (2026-10-18)

The test account's dashboard, deployed from the branch twice with
`union_dashboard.py deploy`: first with `STARGAZER_SAVE_INTERVAL_SECONDS=0`
(`037b45a`), then with the default (`70e333c`). The pods were driven through
their own terminal websocket with `scripts/union_pod.py`, the banner in
Chrome as the test account. Feature file:
`verify-stargazer/features/union-workspace-save.md`.

- **The save at SIGTERM, on its own.** Interval 0: the pod had
  `SG_SAVE_INTERVAL_SECONDS=0` and no `/snapshots`. After writing
  `data/counts.csv`, `data/old.csv`, `lib/helpers.py`, a line in the
  notebook, `.env`, `__marimo__/c.json` and a 150 MB `data/big.bin`, and
  waiting over 12 s, the store held only the notebook as created (788 bytes).
  After Stop and a relaunch (a new pod), `/workspace` held the edited
  notebook and the three files at their paths, and the store exactly those
  four (the notebook now 811 bytes). `.env`, `__marimo__/` and the 150 MB
  file weren't stored.
- **Deletes.** `rm data/old.csv`, Stop, relaunch: gone from the pod and the
  store. With the default interval, `rm -rf data lib` reached the store
  within 8 s.
- **The interval.** Default deploy: the pod had `SG_SAVE_INTERVAL_SECONDS=5`,
  and a file the store had never held was stored within 8 s while the pod
  ran.
- **Big files.** `/__sg__/save-status` listed `data/reads.bam` (2,621,440,000
  bytes). In Chrome the banner read "data/reads.bam (2.4 GB) is over 100 MB,
  so it isn't saved with your workspace...", with the cell. The first deploy
  showed "105 MB", fixed in `70e333c`. The cell, run in the kernel's sandbox
  venv on a random 150 MB file, stored it as
  `.../users/387300641116005877/assets/bafybeia7oarku7qtwiotl3ey6t4vmxtremxozuib6dxs7lc2oxyzkinfce/big2.bin`,
  and `default_client.query({"asset": "data"})` returned its row, owner
  stamped. Not run: `assemble()` from a task pod; the query went through the
  same index client tasks use.
- **Dashboard.** The full page has no Snapshots section or 📸, and says
  "up to 100 MB each; store bigger files as assets."
- **Torn down.** The probe files and notebook deleted, the dashboard
  stopped, nothing active or running in `u-pryce` or `flytesnacks`. The
  150 MB asset stays in the test account's asset store.

One thing seen: a launch straight after a dashboard redeploy reached the old
revision, so the pod got the old interval. Relaunching after the new
revision was ready fixed it. In the feature file's gotchas.

## Open questions

- [x] **Q1. Save only at scale-down, or keep the 5 s pass too?** Decided
      2026-10-17: the interval is configurable, 5 s by default, and 0 saves
      only at scale-down. A pod that dies without SIGTERM loses everything
      since the last pass, so the longer the interval, the more the first
      piece's proof of the scale-down save matters.

## Related tickets

- `public-notebooks`: Publish, which turns a workspace notebook into an asset,
  and the public listing.
- `top-level-notebooks`: the scRNA notebook moves to a top-level `notebooks/`
  folder, and the seeds to `app/`.
- `asset-manager-on-index`: the dashboard as asset explorer and notebook
  launcher, ahead of this ticket in the queue.
- `tus-browser-uploads`: uploads from the user's machine up to 10 GB, through
  the dashboard. Not needed for files already in the workspace.
- `notebook-environment`: notebooks declare their own app environment.
- `bit-for-bit-snapshots`: superseded. Close it as `done`, with an Outcome
  saying so, when this ticket merges.
- `sdk-package`: its step "Decide where the notebooks live" is settled. User
  notebooks live in the workspace, the tutorials stay in the package, and the
  scRNA notebook moves to `notebooks/`.
- `promote-task-cli`: unchanged.
