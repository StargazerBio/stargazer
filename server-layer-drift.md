---
title: server-layer-drift
status: review
priority: low
created: 2026-11-09
pr: 153
---

The notebook image warms the `marimo[lsp]` layer that marimo puts over its server, but the layer's extras are unpinned, so once any of its packages has a newer release uv resolves differently at start, downloads and installs the layer again (43 packages on `debug:notebook-dockerignore` on 2026-11-09, measured), and every pod start pays for it. The same likely holds for the `--with marimo==0.25.1` layer over each kernel (inferred).

Options: lock the layer's resolution at build (`--exclude-newer` at the build's date, set only for marimo's own `uv run` so a user's installs in the terminal aren't held back, or a constraints file), or rebuild the image on a schedule.

Came from [[marimo-server-layer-symlinks]], which fixed the blank editor the stale layer caused.

## Plan

On `fix/server-layer-drift`: the image's warm step resolves marimo's layers with `UV_EXCLUDE_NEWER` at its own date and writes that date to `/opt/uv-exclude-newer`; `launch-notebook.sh` sets `UV_EXCLUDE_NEWER` from it on the `marimo` command only, so the server and kernel layers resolve to the warmed ones. The image's `.bashrc` unsets it, so the terminal's uv isn't held back. pixi ignores the variable, so notebook environments resolve as before.

## Evidence (2026-11-16)

Measured, local `docker run`, linux/amd64. Before: `debug:unpinned-notebook-python` (built 2026-11-11, runtime as on `main`) logs `Downloading ruff (10.1MiB)`, `Installed 43 packages` at start; `loro`, `python-multipart` and `ruff` had releases since. After, the branch built with its warm date backdated to `2026-11-11T16:00:00Z`: no `Downloading`/`Installed` at start (DRIFT-SERVER); the tasks tutorial's kernel layer installs nothing with the image's date, against `Installed 25 packages` without it (DRIFT-KERNEL); `/assets/index-*.js` 200 and the Assets tutorial renders in the built-in browser (DRIFT-EDITOR); `bash -ic` prints `UV_EXCLUDE_NEWER` empty, and the proxy and MCP server don't have it (DRIFT-TERMINAL). A normal build (date `2026-11-16T21:39:40Z`) starts with no installs and serves the editor. In the browser session, the local `/workspace` notebook's kernel didn't start after Run (unexplained; kernel layer checked with marimo's launch command instead).

## Verification recipe: server-layer-drift

A pod started days after its image was built reuses the warmed marimo layers instead of downloading and installing them again.

### Sub-features

- DRIFT-SERVER: the server's `marimo[lsp]` layer installs nothing at start when its dependencies have newer releases than the build.
- DRIFT-KERNEL: a tutorial's kernel layer (`--with marimo==<version>` over its pixi env) reuses the warmed layer.
- DRIFT-EDITOR: the editor still serves (page and its `/assets/*.js` 200).
- DRIFT-TERMINAL: a bash started the way marimo's terminal starts it has no `UV_EXCLUDE_NEWER`.

### How to get to it (user POV)

Open a notebook pod (or `docker run` the image); the editor comes up without the start reinstalling marimo's layer.

### Driving it

Preconditions: an image built from the branch whose warm date is older than a release of a package under `marimo[lsp]`. To make that today, build with the warm step's date backdated (simulates an image built that day): `sed 's/UV_EXCLUDE_NEWER="\$(date -u +%Y-%m-%dT%H:%M:%SZ)"/UV_EXCLUDE_NEWER=<past RFC 3339 date>/' runtime/Dockerfile > /tmp/Dockerfile.backdated && docker buildx build --platform linux/amd64 -f /tmp/Dockerfile.backdated -t sg:drift-backdated --load .`. Confirm drift exists: in the container, `uv pip compile` of `marimo[lsp]==<version>` with and without that `UV_EXCLUDE_NEWER` differ.

1. DRIFT-SERVER: `docker run -d --name sg -p 18080:8080 sg:drift-backdated`; wait for `curl -sf localhost:18080/__sg__/ready`. Passes: `docker logs sg | grep -E 'Downloading|Installed'` is empty. Fails as on `main`: `Installed 43 packages`.
2. DRIFT-KERNEL: in the container, `env=$(pixi install --script <tutorial> 2>&1 | sed -n "s/.*installed at '\(.*\)'\.$/\1/p")`, then `UV_EXCLUDE_NEWER=$(cat /opt/uv-exclude-newer) pixi exec --spec "uv>=0.12" uv run --no-project --python "$env/bin/python" --with marimo==<version> -- python -c 'import marimo'`. Passes: no `Installed` line.
3. DRIFT-EDITOR: `curl -s localhost:18080/ | grep -o '/assets/[^"]*\.js' | head -1`, then that path returns 200.
4. DRIFT-TERMINAL: `docker exec sg bash -ic 'echo "[$UV_EXCLUDE_NEWER]"'` with `-e UV_EXCLUDE_NEWER=x` prints `[]`.

### Gotchas

- `uv run --with` caches its layer keyed on the resolution, so any one changed version (ruff alone, 10 MiB) rebuilds the whole layer: 43 packages, all but the changed ones from cache.
- An image only drifts once a dependency has a release after its build, so a freshly built image shows nothing; backdate the warm date to reproduce.

Related: [[board]], [[marimo-server-layer-symlinks]], [[marimo-sandbox]].
