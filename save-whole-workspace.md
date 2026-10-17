---
title: The workspace saves every file, and snapshots go
status: next
priority: normal
created: 2026-10-16
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
  and Workflows sections. Until then they ship as they do now.
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

**Big files.** `sync_once` in `app/proxy.py` reads each file whole and hashes
it on every pass (`_digest(path.read_bytes())`), then uploads it from memory.
That's fine for notebooks. A multi-gigabyte data file would be read in full
on every pass, and loading it into memory could OOM the pod. So the proxy
compares size and modification time before reading a file, and streams
uploads from disk.

**Deletions.** Today a deleted file isn't deleted from the store (notebooks
are deleted from the dashboard), so a file deleted in the terminal would come
back at the next launch. A save also deletes the stored copy of a file that's
gone from `/workspace`, but only for files this pod hydrated or saved. If the
hydrate fails, the pod starts with an empty workspace (logged, not fatal), and
a plain mirror would then wipe the store.

**Hydrating.** At launch the pod downloads every object under the prefix to
its path under `/workspace`. `/snapshots` goes.

**When it saves** is Q1. The proxy already saves at scale-down: on Knative's
SIGTERM, the proxy's FastAPI shutdown hook runs a last pass. What's known:

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

- [ ] Prove the save at scale-down on Union, on its own, before anything
      depends on it: write a file into a running pod's `/workspace` straight
      after a save pass, let the pod scale to zero, and read the pod's logs
      for `[sg] saved` after SIGTERM, then reopen. Read the pod's
      `terminationGracePeriodSeconds` from the EKS audit log.
- [ ] Proxy: save and hydrate every file, with the new prefix, the skips,
      the size and modification-time check, streamed uploads, and deletions.
      Then whatever Q1 decides about the 5 s pass. Tests in
      `tests/unit/test_proxy.py`:
  - a CSV written to `data/` → saved at `workspace/data/counts.csv`, and
    hydrated back to `/workspace/data/counts.csv`
  - a file under `__marimo__/` or `__pycache__/`, or a dotfile → not saved
  - an unchanged file whose size and modification time match → not read on
    the next pass
  - a hydrated file deleted from `/workspace` → deleted from the store at
    the next save
  - a store object the pod never hydrated (the hydrate failed) → kept
- [ ] `app/workspace_store.py`: the `workspace/` prefix. A test: a nested
      `lib/helpers.py` and `data/counts.csv` under the prefix → not listed as
      notebooks.
- [ ] Remove snapshots: `/workspace/snapshot`, `/snapshot/delete`, the
      snapshot sources of copy and launch, the Snapshots section in
      `app/templates/dashboard.html`, `src/stargazer/notebooks/snapshots/`,
      `PUBLIC_SNAPSHOTS_DIR` and `PublicSnapshot`, `SNAPSHOT_NOTEBOOK_DIR`, the
      `snapshots_uri` layout, and the snapshot tests in
      `tests/unit/test_app.py`.
- [ ] Docs:
  - `docs/architecture/notebook.md`: the types table, the archetypes,
    Promotion Paths (freeze goes, and promotion outside the dashboard
    stays)
  - `docs/architecture/app.md`: topology, "Saving just works", the Snapshots
    section
  - `.opencode/reference/architecture/app_internals.md`: Pod Hydrate & Save,
    snapshots, copy, and the route table
  - If a doc is added or removed, update the `zensical.toml` nav. If the
    README mentions snapshots, list that drift in the PR and don't edit the
    README.
- [ ] Verify on Union with the test account (`verify-stargazer`; the closest
      existing feature is `union-main-img`):
  - edit a notebook and write `data/counts.csv` from the terminal, let the
    pod scale to zero, reopen → both are there
  - delete a file from the terminal, scale to zero, reopen → it stays
    deleted
  - the dashboard has no Snapshots section

  Then add a feature file for saving the workspace, and stop every app the
  check started.

## Open questions

- [ ] **Q1. Save only at scale-down, or keep the 5 s pass too?** Saving only
      at scale-down means no writes while the user works. A pod that dies
      without SIGTERM loses the whole session, not the last 5 s, and
      everything changed in the session has to upload in the grace period.
      The 5 s pass writes a file only when it changed, so the cost of
      keeping it is a stat of each file every 5 s, plus a partly written
      large file being uploaded more than once while it grows. Decide after
      the first piece measures the scale-down save.

## Related tickets

- `public-notebooks`: Publish, which turns a notebook into an asset, the
  public listing, and the tutorials and scRNA notebook as public notebooks.
- `asset-manager-on-index`: the dashboard as asset explorer and notebook
  launcher, ahead of this ticket in the queue.
- `notebook-environment`: notebooks declare their own app environment.
- `bit-for-bit-snapshots`: superseded. Close it as `done`, with an Outcome
  saying so, when this ticket merges.
- `sdk-package`: its step "Decide where the notebooks live" is settled. User
  notebooks live in the workspace, and the tutorials and scRNA notebook
  leave the package as public notebooks.
- `promote-task-cli`: unchanged.
