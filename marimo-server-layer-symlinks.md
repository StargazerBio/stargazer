---
title: marimo-server-layer-symlinks
status: done
priority: high
created: 2026-11-07
pr: 141
---

In the image `debug:notebook-dockerignore` (main at efc2e4a), run locally with `launch-notebook.sh edit /stargazer/src/stargazer/notebooks/tutorials/execution.py`, the editor page is blank: every `/assets/*.js` request returns 404, and marimo logs `Assets directory contains symlinks but follow_symlink=false`.

The server starts under `uv run --with marimo[lsp]==0.25.1`, and the image warms that layer at build time. At start the warmed layer wasn't reused: uv logged `Downloading ruff (10.1MiB)` and `Installed 42 packages`, so `marimo[lsp]`'s unpinned extras resolved to a newer release than the build's. The rebuilt layer is linked with the runtime's `UV_LINK_MODE=symlink`, so `marimo/_static/assets/*` are symlinks into `/opt/uv-cache/archive-v0/`, which marimo won't serve (measured: `ls -la` in the running container; the editor loads with `-e UV_LINK_MODE=copy`).

A hosted pod runs the same launch, so it likely shows the same blank editor once a new release of one of the layer's packages is out (inferred, not driven). Options to weigh: pin the server layer's resolution (a lock, or `--exclude-newer` at the build's date), set `[server] follow_symlink = true` in `runtime/marimo.toml`, or link the server layer by copy.

Seen while working on [[marimo-autoadd-headers]].

## Plan

On `fix/marimo-server-layer-symlinks`: `[server] follow_symlink = true` in `runtime/marimo.toml`, which fixes the blank editor however the layer is linked. Pinning the layer's resolution, so a stale layer doesn't download and install at every start, is ticket [[server-layer-drift]].

## Evidence (2026-11-09)

`ghcr.io/stargazerbio/debug:notebook-dockerignore` run locally, its layer stale (`Installed 43 packages` at start). As built: `GET /assets/index-DafnX1Xx.js` 404, with the `follow_symlink=false` error logged. With the branch's `marimo.toml` mounted over the image's: 200, no symlink error, and the Assets tutorial's editor renders in the built-in browser (measured).

## Verification recipe

SERVER-SYMLINKS: the editor's assets load on an image whose server layer is rebuilt at start.

1. Pick an image old enough that its start logs `Installed <n> packages` (any built before the latest release of a package under `marimo[lsp]`). `docker run -d --name sg -p 18080:8080 -v $PWD/runtime/marimo.toml:/home/flyte/.config/marimo/marimo.toml:ro <image>`; wait for `/__sg__/ready`.
2. `curl -s localhost:18080/ | grep -o '/assets/[^"]*\.js' | head -1`, then `curl -o /dev/null -w '%{http_code}'` that path. Passes: 200, and `docker logs sg` has no `follow_symlink=false`. Fails as on `main` (no mount): 404 and the error.

## Outcome

PR 141 merged 2026-11-10 with no review comments. Shipped: `[server] follow_symlink = true` in `runtime/marimo.toml`, so the editor's assets load however the server layer is linked. Verified on a stale-layer image run locally with the branch's `marimo.toml` mounted (see Evidence). Left: a stale layer still downloads and installs at every start, ticket [[server-layer-drift]]; a hosted pod wasn't driven.

Related: [[board]], [[marimo-autoadd-headers]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
