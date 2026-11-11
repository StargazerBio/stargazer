---
title: unpinned-notebook-python
status: review
priority: high
created: 2026-11-09
pr: 143
---

A notebook whose header doesn't pin Python under `[tool.pixi.dependencies]` gets Python 3.15 in the pixi sandbox, and its kernel never starts: marimo's runtime overlay (`pixi exec --spec uv>=0.12 uv run --no-project --python <env python> --with marimo==0.25.1`) finds no cp315 wheel for `loro`, which marimo depends on, builds its sdist, and PyO3 refuses 3.15 ("newer than PyO3's maximum supported version (3.14)"). The editor sits on "Starting kernel…" with no error in the notebook.

Measured on the tenant on 2026-11-09, as the test account, with a notebook image built from `main` plus run-modes (`ghcr.io/stargazerbio/debug:run-modes`): a workspace notebook created from the dashboard's Blank seed hit it. The dashboard pins release 2026.10.30, whose `templates/blank.py` header is uv-style (`requires-python = ">=3.14"`, `[tool.uv.sources]`) with no pixi Python pin. The same notebook's kernel starts on the 2026.10.30 image, which predates the pixi sandbox, and a built-in notebook from `main` (pinning `python = "3.14.*"`) starts on the new image.

So every workspace notebook saved before the pixi sandbox, and any community notebook without the pin, breaks once the dashboard moves to a release with the pixi sandbox. Options to weigh: the launch pins Python when a header doesn't (an overlay constraint or a default `python` dependency), or the dashboard rewrites old headers on upgrade. Verify by creating a notebook from an old seed on the new image and seeing its kernel start.

## Plan

On `fix/unpinned-notebook-python`: the launch pins Python when a header doesn't, the first of the ticket's options, since it also covers notebooks from elsewhere.

- [x] `pin_python()` in `runtime/proxy.py`, with unit tests in `tests/unit/test_pin_python.py`: a header with no `python` under `[tool.pixi.dependencies]` gets one at the runtime's own minor version, in that table, in a new table before the header's close, or in a new header. A pinned header, one that doesn't parse and a missing file are left alone.
- [x] `launch-notebook.sh` runs it after hydrate, before marimo.
- [x] `docs/architecture/runtime.md`.
- [ ] The ticket's check: an old-seed notebook's kernel starts on a pod.

## Evidence (2026-11-09)

- Unit tier: 286 passed.
- `ghcr.io/stargazerbio/debug:dispatch-installed-bundle` run locally on a workspace notebook with release 2026.10.30's Blank header, with the two commands marimo's sandbox makes. As built: `pixi install --script` gives Python 3.15.2 and `uv run --python <env> --with marimo==0.25.1` fails building `loro` with the PyO3 error. With the branch's `proxy.py` and `launch-notebook.sh` mounted: the launch added the pin to the workspace file, the environment is Python 3.14.10 and the marimo layer imports (measured).
- Not reached: the kernel starting in the editor. In local containers the editor's kernel started for no notebook, with or without the change, and the cause wasn't found. PR 143 is a draft until an old-seed notebook is opened on the tenant.

Left out: a notebook that didn't hydrate (marimo creates its blank after the pin runs), and an old header's SDK source, ticket [[old-header-sdk-source]].

## Verification recipe: an old-seed notebook on a pod

A workspace notebook created from a seed that predates the pixi sandbox (uv-style header: `requires-python`, `[tool.uv.sources]`, no pixi tables) opens in the editor, its kernel starts on the image's Python, and it imports the image's SDK rather than PyPI's.

### Sub-features

- **PIN**: the launch adds `python = "<image minor>.*"` under `[tool.pixi.dependencies]`.
- **SDK**: the launch copies the `[tool.uv.sources]` path for `stargazer-bio` into `[tool.pixi.pypi-dependencies]`.
- **KERNEL**: the editor's kernel starts and runs a cell.

### How to get to it (user POV)

The dashboard's Workspace section: create a notebook from Blank, open it in edit.

### Driving it

Preconditions: an infra checkout whose `stargazer-bio` pin is a release with a uv-style Blank seed (2026.10.30), with `.flyte/union.yaml` linked and `tenant.env` loaded; the built-in browser signed in to the console as the test account.

1. From the stargazer worktree: `docker buildx build --platform linux/amd64 -f runtime/Dockerfile -t ghcr.io/stargazerbio/debug:unpinned-notebook-python --push .`
2. From infra: `STARGAZER_NOTEBOOK_IMAGE=ghcr.io/stargazerbio/debug:unpinned-notebook-python uv run python .claude/skills/verify-dashboard/scripts/union_dashboard.py deploy`. `check <dashboard app>` shows the debug image's digest.
3. In the dashboard, create a Blank workspace notebook under a fresh name and open it in edit. Passes **KERNEL**: the kernel leaves "Starting kernel…" and a cell runs.
4. In a cell:

   ```python
   import sys, importlib.metadata as md
   dist = md.distribution("stargazer-bio")
   (sys.version, dist.version, dist.read_text("direct_url.json"),
    open(__file__).read().split("# ///\n")[0])
   ```

   Passes **PIN**: Python is the image's minor (3.14), and the header shows the pin. Passes **SDK**: `direct_url.json` names `file:///stargazer` (a PyPI install has none) and the header shows the `[tool.pixi.pypi-dependencies]` entry beside the untouched `[tool.uv.sources]`.
5. `union_dashboard.py teardown`; its live runs print `[]`.

### Gotchas

- In local containers the editor's kernel didn't start for any notebook, with or without the change (2026-11-09), so KERNEL is only reachable on the tenant.
- A workspace notebook is a copy of its seed at creation: an existing old notebook works too, a new one needs the old pin in infra.

Related: [[board]], [[pixi-notebook-sandbox]], [[run-modes]], [[marimo-sandbox]].
