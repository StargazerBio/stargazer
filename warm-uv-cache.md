---
title: warm-uv-cache
status: done
pr: 125
priority: normal
created: 2026-10-31
---

Every notebook pod and every `docker run` of the Stargazer image downloads about 100 packages from PyPI before its first notebook's kernel starts. That's what `marimo --sandbox` is for: each notebook gets a venv built from its own PEP 723 header, so notebooks can need different things (`stargazer-bio` vs `stargazer-bio[bio]`) and the kernel stays out of the runtime venv. But nothing from those venvs is in the image. Both `uv` installs in `runtime/Dockerfile` run with `--no-cache` and as root, so the `flyte` user starts every container with an empty uv cache at `~/.cache/uv`. Ticket [[notebook-pod-ephemeral-storage]] measured 101 to 111 packages installed per notebook on a hosted pod.

Keep `--sandbox` and the per-notebook headers. Bake a warm uv cache into the image instead, so a kernel's venv is mostly a copy from local disk and only packages a user adds to a header come from PyPI.

## How the sandbox uses uv (marimo 0.25.1, read in its source)

- The server starts once. A kernel's venv is built when its notebook first opens, with `uv sync --script <notebook> --compile-bytecode`, and the kernel starts under `uv run --active --no-project --with marimo==0.25.1`. The `--with` layer is a cached side environment; that it's built once and shared by every kernel is inferred from marimo's docstring.
- Opening another notebook from the sidebar starts another kernel with its own venv.

## What uv reuses (measured locally, uv 0.13.5, `UV_LINK_MODE=copy`, throwaway `UV_CACHE_DIR`)

- Venvs are per file: `environments-v2/<name>-<hash>`, so two scripts with identical headers still get two venvs.
- The same script synced again reuses its venv (`Checked 2 packages in 0.05ms`).
- A second script with the same deps downloads nothing; resolution and wheels both come from cache (`Resolved 2 packages in 0.52ms`, no `Prepared`).
- A script with one extra dep downloads only that one (`Prepared 1 package`).

So within one container the second notebook is already mostly local. The cost is the first notebook of every container, and on the devbox and Union that's every pod start.

## Plan

- [x] Measure the baseline. Locally (fresh `docker run`, replaying marimo's uv calls): the Assets tutorial resolves and downloads 76 packages and the kernel's marimo layer 25 more, ~7.8 s; the scRNA notebook opened second still downloads 50. Hosted (release `v2026.10.30`, test account, 1 CPU): 16 large wheels downloaded, `Installed 108 packages in 26.67s`, `Bytecode compiled 4826 files in 12.00s`; uvicorn up 20:19:18, editor connected 20:20:07, ~49 s.
- [x] Warm the cache at build time: `UV_CACHE_DIR=/opt/uv-cache` owned by `flyte`; each built-in notebook's venv prebuilt at both paths it opens from, hardlinked to the cache within one layer; the server's `--with marimo[lsp]` layer warmed too (it downloaded `ruff` on every start).
- [x] Measure again. Hosted, debug image `ghcr.io/stargazerbio/debug:warm-uv-cache`: no downloads; the notebook's sync takes 1.4 s and 1.3 s on two pods (`Resolved 93 packages in 155ms`, `Bytecode compiled 4600 files in 250ms`), and the setup cell ran in 374 ms. Locally: ~1.8 s, and it works with `--network none`. Image: +2.4 GB uncompressed (~1.1 GB cache, ~1.2 GB bytecode in the 14 venvs), 1.17 → 2.35 GB compressed; the first pull on a fresh node took 83 s.
- [x] Update `docs/architecture/runtime.md`'s list of what the image holds.
- [x] Lean out the image, after the first pass doubled it: drop micromamba and the bioinformatics tools (1.2 GB; a cluster run gets them from its task's image, a notebook that runs one in its own process declares it in `main_env`), warm only notebooks on the core SDK (one needing the `bio` extra downloads it on first open), and prebuild venvs only at the path a hosted pod opens built-ins from (locally they build from the cache). Measured locally: 4.56 GB uncompressed (release `v2026.10.30` 4.47 GB), cache 923 MB of packages + 453 MB of bytecode in 6 venvs; Assets installs from the cache with no downloads (`Installed 93 packages in 1.24s`, `Bytecode compiled 4600 files in 680ms`); the Execution tutorial's local run returns its 3 summaries with no tools in the image.
- [x] Measure the lean image hosted (test account, Assets tutorial, edit): 1.11 GB compressed against the release's 1.17 GB; first pull on a node 35.7 s (the full-cache image took 83 s); no downloads, `Resolved 93 packages in 9ms`, the editable SDK rebuilt in 3.78 s (0.86 s on earlier pods), `Bytecode compiled 4600 files in 200ms`; kernel up 5 s after the browser connected; setup cell ran in 500 ms.
- [x] Let notebooks install conda packages: micromamba with `/opt/conda` owned by `flyte`, last on every process's path, conda-forge and bioconda as channels. Measured locally: `micromamba install samtools` as the notebook user took 16 s, and a running kernel's cell printed `samtools 1.25`. Image 4.59 GB uncompressed.
- [x] Keep conda installs across containers: the channels moved to `/etc/conda/.condarc`, so a mount at `/opt/conda` doesn't hide them. Measured locally: with a named volume or a macOS host folder at `/opt/conda`, samtools installed in one container ran in the next; with a folder owned by root, the install fails (`Permission denied [/opt/conda/conda-meta]`), so on Linux a host folder must be writable by user 1000. Documented in Getting Started's Install Tools.
- [x] Document where a notebook's packages and tools come from, hosted, locally and on the cluster (`docs/architecture/notebook.md`, the agent's `AGENTS.md`). Deferred: [[local-notebook-images]], [[layered-notebook-image-cache]].

## Findings

- **marimo 0.25.1 edits a notebook's header on open.** Before syncing, it runs `uv add --script <notebook> marimo` on a header without `marimo`, which resolves the latest marimo (0.25.2 at the time) and would put every prebuilt venv behind marimo's next release. The built-in headers now list `marimo`, so the sandbox leaves them alone.
- **Drift is mostly a non-issue.** With a venv already present, uv prefers the installed versions over newer ones on PyPI. With index responses past their 600 s max-age, resolution revalidates in ~300 ms instead of ~40 ms (measured locally, image 20 min old). No lock needed.
- **Disk.** A prebuilt venv lives in the image, not the pod's writable layer, so a built-in notebook no longer writes its venv to the pod's disk at all.
- **The editable `stargazer-bio` rebuilds on every open** (~0.5 s locally, ~0.8 s hosted): uv keys it on `/stargazer/src`'s mtime, and its own build writes the egg-info there. Left as is.
- **Declared images** are built `FROM` the Stargazer image, so they carry `/opt/uv-cache` and `UV_CACHE_DIR` (inferred, not driven).

## Outcome

Shipped in PR 125 (merge `51da133`, 2026-11-04). The notebook image bakes a warm uv cache at `/opt/uv-cache` with a prebuilt venv for each built-in notebook at its hosted path, drops the bioinformatics tools, and keeps micromamba so a notebook can `micromamba install` a conda package (channels in `/etc/conda/.condarc`, `/opt/conda` owned by the runtime user). Verified again after merging main, on Union as the test account with the final image (`debug:warm-uv-cache@sha256:78c59f82…`): browser connect to kernel in 1.9 s, nothing downloaded (`Resolved 93 packages in 10ms`), `micromamba install samtools` in 17.1 s with `samtools 1.25` running; locally offline, a venv from the cache in 2.7 s. Left: ticket [[pixi-notebook-sandbox]] replaces the uv sandbox, its cache and micromamba with pixi; [[layered-notebook-image-cache]] and [[local-notebook-images]] as before; the editable SDK still rebuilds on each open (0.5–3.8 s). No review comments.

## Verification recipe

The fresh-container cold start, before and after, locally and hosted.

- Locally: build the image, `docker run -p 18080:8080` it, open it in the browser and read `docker logs` for the sandbox's `Resolved`/`Prepared`/`Installed` lines (a warm image has no `Downloading` and `Prepared 1 package`, the editable SDK). Replaying marimo's calls in a fresh container times it without a browser: `uv sync --script <notebook> --compile-bytecode`, then `uv run --active --no-project --python <venv python> --with marimo==0.25.1 -- python -c 'import marimo, stargazer'` with `VIRTUAL_ENV` set to the venv. `--network none` proves nothing is fetched.
- Hosted: push the branch image to `ghcr.io/stargazerbio/debug:<slug>`, deploy the test dashboard with `STARGAZER_NOTEBOOK_IMAGE` set to it (infra's `verify-dashboard`), launch the Assets tutorial in edit mode, open it, and read the pod's log with read-only `kubectl logs -c nb-assets-edit` (the container is named after the app). Then redeploy the dashboard on the release image and tear down.

Related: [[board]].
