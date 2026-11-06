---
title: community-catalog-pixi-headers
status: doing
priority: normal
created: 2026-11-04
---

With [[pixi-notebook-sandbox]] merged, notebook environments come from pixi, but two places still describe the uv sandbox:

- The community notebooks' `catalog.yaml` pins each notebook's header from before pixi. StargazerBio/community-notebooks#4 rewrites the headers: germline declares its tools. Once it merges, bump the catalog's pins to it.
- infra's `app/per_notebook.py` and `.claude/reference/architecture/app_internals.md` describe a notebook's "sandbox venv, uv cache". Rewrite both for pixi. It's a small doc edit, so it rides on the next infra PR.

## Plan

- [x] Docs: `app/per_notebook.py`'s docstring and `app_internals.md` (the
      paragraph on ephemeral storage, and the parenthetical on marimo
      pinning in the Workspace paragraph) describe marimo's pixi sandbox
      building each notebook an environment from its header, the image's
      warm cache, and headers listing `marimo` themselves. Rides on infra's
      `feat/community-explorer-listing` ([[community-explorer-listing]], infra PR 30).
- [ ] Catalog: after StargazerBio/community-notebooks#4 merges (open as of
      2026-11-06), set each `catalog.yaml` commit to the one that last
      touched its notebook on `main`, as a commit to the repo's `main`.

Related: [[board]], [[pixi-notebook-sandbox]], [[germline-notebook]], [[marimo-sandbox]].
