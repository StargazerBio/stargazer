---
title: community-catalog-pixi-headers
status: backlog
priority: normal
created: 2026-11-04
---

With [[pixi-notebook-sandbox]] merged, notebook environments come from pixi, but two places still describe the uv sandbox:

- The community notebooks' `catalog.yaml` pins each notebook's header from before pixi. StargazerBio/community-notebooks#4 rewrites the headers: germline declares its tools. Once it merges, bump the catalog's pins to it.
- infra's `app/per_notebook.py` and `.claude/reference/architecture/app_internals.md` describe a notebook's "sandbox venv, uv cache". Rewrite both for pixi. It's a small doc edit, so it rides on the next infra PR.

Related: [[board]], [[pixi-notebook-sandbox]], [[germline-notebook]], [[marimo-sandbox]].
