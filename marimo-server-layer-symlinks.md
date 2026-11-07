---
title: marimo-server-layer-symlinks
status: backlog
priority: high
created: 2026-11-07
---

In the image `debug:notebook-dockerignore` (main at efc2e4a), run locally with `launch-notebook.sh edit /stargazer/src/stargazer/notebooks/tutorials/execution.py`, the editor page is blank: every `/assets/*.js` request returns 404, and marimo logs `Assets directory contains symlinks but follow_symlink=false`.

The server starts under `uv run --with marimo[lsp]==0.25.1`, and the image warms that layer at build time. At start the warmed layer wasn't reused: uv logged `Downloading ruff (10.1MiB)` and `Installed 42 packages`, so `marimo[lsp]`'s unpinned extras resolved to a newer release than the build's. The rebuilt layer is linked with the runtime's `UV_LINK_MODE=symlink`, so `marimo/_static/assets/*` are symlinks into `/opt/uv-cache/archive-v0/`, which marimo won't serve (measured: `ls -la` in the running container; the editor loads with `-e UV_LINK_MODE=copy`).

A hosted pod runs the same launch, so it likely shows the same blank editor once a new release of one of the layer's packages is out (inferred, not driven). Options to weigh: pin the server layer's resolution (a lock, or `--exclude-newer` at the build's date), set `[server] follow_symlink = true` in `runtime/marimo.toml`, or link the server layer by copy.

Seen while working on [[marimo-autoadd-headers]].

Related: [[board]], [[marimo-autoadd-headers]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
