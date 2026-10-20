---
title: Open a notebook from GitHub in the workspace
status: backlog
priority: normal
created: 2026-10-17
blocked_by:
  - top-level-notebooks
---

Notebooks in the repo's top-level `notebooks/` folder (ticket
`top-level-notebooks`) don't ship in the notebook image, so a dashboard user
can't run one. Bring a notebook from GitHub into the user's workspace, where
it's saved like any other file (ticket `save-whole-workspace`). One shape is a
box on the dashboard that takes a GitHub link and drops the file into the
workspace. That works for notebooks in anyone's repo, not only this one, and a
link pinned to a commit gets the same file every time.

## Open questions

- Does the dashboard also list the repo's `notebooks/`, or only take links?
- A notebook that imports files beside it needs its folder, not one file.
- Not checked: whether pods can reach GitHub. If they can, downloading the
  raw file from the pod's terminal works in the meantime.
