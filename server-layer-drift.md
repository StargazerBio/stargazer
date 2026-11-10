---
title: server-layer-drift
status: backlog
priority: low
created: 2026-11-09
---

The notebook image warms the `marimo[lsp]` layer that marimo puts over its server, but the layer's extras are unpinned, so once any of its packages has a newer release uv resolves differently at start, downloads and installs the layer again (43 packages on `debug:notebook-dockerignore` on 2026-11-09, measured), and every pod start pays for it. The same likely holds for the `--with marimo==0.25.1` layer over each kernel (inferred).

Options: lock the layer's resolution at build (`--exclude-newer` at the build's date, set only for marimo's own `uv run` so a user's installs in the terminal aren't held back, or a constraints file), or rebuild the image on a schedule.

Came from [[marimo-server-layer-symlinks]], which fixed the blank editor the stale layer caused.

Related: [[board]], [[marimo-server-layer-symlinks]], [[marimo-sandbox]].
