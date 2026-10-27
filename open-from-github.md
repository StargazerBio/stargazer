---
title: Open a notebook from GitHub in the workspace
status: doing
priority: normal
created: 2026-10-17
---

A notebook that isn't in the SDK, such as one in someone else's repo, doesn't
ship in the notebook image, so a dashboard user can't run it. Bring a notebook
from GitHub into the user's workspace, where it's saved like any other file
(ticket `save-whole-workspace`). One shape is a box on the dashboard that
takes a GitHub link and drops the file into the workspace. That works for
notebooks in anyone's repo, not only this one, and a link pinned to a commit
gets the same file every time.

## Decisions

- **One file** (decided 2026-10-26). A link to a `.py` file becomes a
  top-level workspace notebook, the way Copy brings in an SDK notebook. A
  notebook that imports files beside it is out of scope here (ticket
  `open-github-folder`).
- **Pods reach GitHub** (measured 2026-10-26). A task pod in `u-pryce` got
  HTTP 200 from `raw.githubusercontent.com`, `api.github.com` (unauthenticated)
  and `codeload.github.com` (run `u8x6jd7fn9nw4zmf5zfg`). The dashboard and
  notebook pods run in the same cluster, so they're expected to reach it too
  (inferred). Until the box ships, downloading the raw file from a notebook
  pod's terminal is the workaround.
- **Built** (2026-10-26). An **Open from GitHub** tile in the Workspace grid
  posts the link to `/workspace/github`. Links are `github.com/.../blob/...`
  or `raw.githubusercontent.com/...` `.py` files only; the dashboard fetches
  the raw file itself, never follows a redirect, and caps it at 1 MB. A file
  with no `main_name` is named after its file stem. A slug over the launchable
  length is refused, as create does.

## Verification recipe: Open a notebook from GitHub

A dashboard user pastes a GitHub link to a marimo notebook's `.py` file into
the Workspace grid's **Open from GitHub** tile; the file appears as a
workspace tile that launches like any other. A bad link, a missing file, a
file too big or a non-notebook gets a message instead.

### Sub-features

- `gh-open`: a `blob` link pinned to a commit becomes a workspace tile, stored
  under the user's workspace.
- `gh-run`: the opened notebook launches and its cells run.
- `gh-errors`: a non-GitHub link and a missing file each show their message,
  and nothing is stored.

### How to get to it (user POV)

- Dashboard → Workspace → the dashed **Open from GitHub** tile beside the
  New-notebook tile.

### Driving it

Preconditions: the `verify-stargazer` Union tenant preconditions; the
built-in browser pane signed in to the console as the test account.

- **Deploy.** `STARGAZER_TARGET=union uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy`, with infra's `tenant.env` exported. Open the printed URL from the console page with `location.href`.
- **Open (`gh-open`).** Paste `https://github.com/StargazerBio/stargazer/blob/72dd7dbede4fbfbae0f7e82d948ff14642007bd5/src/stargazer/notebooks/tutorials/assets.py` into the tile and click **Open from GitHub**. A tile titled `assets` appears before the New-notebook tile, and stays after a reload.
- **Run (`gh-run`).** Click **Run** on the new tile, then **Open: Run Mode**: the tutorial's sections render with no error cell.
- **Errors (`gh-errors`).** From the dashboard page, `fetch('/workspace/github', {method: 'POST', body: new URLSearchParams({link})})` with `https://gitlab.com/a/b/blob/c/x.py` gives 400 and the "Paste a link to a .py file on GitHub" message; with the assets link's path changed to `nope.py`, 404 and "wasn't found on GitHub". (An alert from the tile shows the same text.)
- **Teardown.** Delete the `assets` workspace tile, then `union_dashboard.py teardown`: `live runs: []`.

### Gotchas

- Every shipped tutorial's file stem is also its tile's slug, so an opened
  tutorial shares its app name (`nb-assets-run`) with the shipped one
  (ticket `workspace-slug-shadows-shipped`). Stop the shipped tutorial first.
