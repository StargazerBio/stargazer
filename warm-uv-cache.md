---
title: warm-uv-cache
status: backlog
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

- [ ] Measure the baseline: a fresh `docker run` of the current image, the time from start to the Assets tutorial's kernel running, and how many packages it downloads; the same for the scRNA notebook (the `bio` extra) opened second.
- [ ] Warm the cache at build time: a fixed `UV_CACHE_DIR` owned by `flyte` (so the runtime user can write to it, and a hosted pod's home isn't the only place it can live), filled by syncing the headers the built-in notebooks use (`stargazer-bio` and `stargazer-bio[bio]` from `/stargazer`, plus the `--with marimo==0.25.1` layer) with the same uv binary the runtime uses.
- [ ] Measure the image size it adds and the cold start again, locally and on a hosted pod with the test account.
- [ ] Update `docs/architecture/runtime.md`'s list of what the image holds.

## Open questions

- **Drift.** The headers aren't locked, so a sync resolves to the latest versions PyPI has. Once a dependency releases after the image was built, the pod downloads the newer version anyway, and the cache only helps for what hasn't moved. Check whether `uv sync --script` honours a lock beside the script (`uv lock --script`) and whether the built-in notebooks should ship one, or whether `exclude-newer` at build time is enough. Also check that uv's cached index responses expiring doesn't put a network round trip back on every start.
- **Disk.** `UV_LINK_MODE=copy` means each venv is a full copy on the pod's disk, cache or not. Hardlinking out of an image layer would most likely copy up anyway on overlayfs (a guess). Check whether pre-building the venvs themselves at the paths notebooks open from (`/workspace/notebooks/...` locally) is possible, given the venv's hash is keyed on the script's path.
- **Declared images.** A notebook that declares its own image (`main_img` built on the Stargazer image) should inherit the cache. Confirm it does.

## Verification recipe

The fresh-container cold start, before and after, locally and hosted. Locally: build the image, `docker run` it with nothing cached, and time from start to the Assets tutorial's first cell output, counting the downloads in marimo's sync output. Hosted: open a tutorial in edit mode as the test account and read the pod log's install lines and timings. Then deactivate the app.
