---
title: header-declared-pod
status: later
priority: normal
created: 2026-11-16
---

A notebook says what it runs in from three places: its script header (conda and PyPI packages), `main_env` in its setup block (the pod's image and size) and a task environment (its own tasks). Since the pixi sandbox, the header covers every package and command-line tool, so `main_env` adds two things: system packages conda doesn't have, and the pod's CPU and memory. Supporting it costs, in infra (line counts measured 2026-11-16):

- `app/notebook_meta.py` (266 lines) and `app/notebook_environment.py` (103): finding the setup block with `ast`, evaluating the `main_env` expression, rewriting the block from the tile's gear.
- The launch's build path in `app/admin_app.py` (`_serve_notebook`, `_settle_launch`, `_keep_failure`, `_serve_built`, `_forget_build`) and the launch rows in the state table, so a build outlives a request and a redeploy.
- Pinning a built image by digest (`app/image_digest.py`, 113 lines, its ECR branch).
- In this repo, `notebook_base`, `notebook_env` and their helpers in `notebooks/__init__.py`, the template's Pod section, and the Notebook Environment section of `docs/architecture/notebook.md`.

The idea: the pod is declared as plain values in the header's `[tool.stargazer]` table, which already holds `owners`:

```toml
# [tool.stargazer]
# name = "Variant QC"
# description = "bcftools stats on new calls."
# cpu = 2
# memory = "4Gi"
```

The dashboard reads it with `tomllib` and runs no notebook code. Every notebook pod runs the release's image, so nothing builds at launch. A notebook that needs a system package conda lacks runs on an image its author builds on the Stargazer image and names in the deploy, which is a docs page, not a code path.

To settle before it's `backlog`:

- Whether any notebook in use needs an apt package that conda-forge and bioconda don't carry. None of the built-in or community notebooks does (read, not surveyed across workspaces).
- What the gear becomes: a small form over those values.
- Existing workspace notebooks carry `main_name`, `main_description` and `main_env` in their setup blocks. With no backwards compatibility they'd need a one-time rewrite, or the dashboard reads the old strings for a release.
- Tickets this would close or change: [[prebuilt-notebook-environment]], [[layered-notebook-image-cache]], [[local-notebook-images]].

Related: [[board]], [[prebuilt-notebook-environment]], [[layered-notebook-image-cache]], [[local-notebook-images]], [[launch-build-state]], [[notebook-image-digest]].
