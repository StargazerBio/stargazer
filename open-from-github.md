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
