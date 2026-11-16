---
title: sdk-front-door
status: review
priority: high
created: 2026-11-16
pr: 150
---

A researcher's notebook should import what it needs from `stargazer`, and its setup block should hold only what they'd change. From an architectural scan of `main` (2026-11-16):

- `src/stargazer/__init__.py` exports `PinataClient`, `StorageClient`, `default_client` and `get_client`, which a notebook never touches, and none of what one does. The built-in and community notebooks import from eight submodules (measured, `grep` over their `from stargazer…` lines): `assets.asset`, `assets.scrna`, `assets.reference`, `config`, `notebooks`, `notebooks.ui`, `bundles`, `tasks.scrna.env`.
- Every notebook calls `init_flyte()` in its first cell (6 of 6 that dispatch).
- `templates/basic.py`'s setup block imports `STARGAZER_ENV_VARS`, `STARGAZER_SECRETS`, `notebook_image` and `notebook_env` before any of the user's own code. PR 149 (ticket [[bare-task-environments]]) drops the env vars; this ticket starts from what it leaves.

## Plan

- [x] `stargazer/__init__.py` exports `Asset`, `assemble`, `fetch_bundle`, `init_flyte` and the asset types; the storage clients stay importable from `stargazer.utils`. Check the import layers (`src/stargazer/ruff.toml`) allow it, and that infra's imports of the old names still resolve or are changed in the same pin bump.
- [x] `dispatch` and `run_location` import marimo, which the core doesn't depend on, so they can't be imported eagerly at the root. Settle: leave them at `stargazer.notebooks.ui`, or expose them through a module `__getattr__`. They stay at `stargazer.notebooks.ui`.
- [x] `dispatch` initializes Flyte on first use when nothing has, so a notebook doesn't call `init_flyte()` itself. It stays public for SDK users.
- [x] The templates, tutorials and `runtime/notebook_agent.md` use the short imports. The community notebooks follow in their own repo.
- [x] Docs: the guides' examples, `docs/architecture/notebook.md`. The task and workflow guides describe modules inside the package, which keep importing from the defining submodule; the root is the top layer.

Verify by opening the basic template from the image, hosted and locally, and running its workflow both ways.

## Verification recipe: sdk-front-door

A notebook imports `Asset`, the asset types, `assemble`, `fetch_bundle` and `init_flyte` from `stargazer`, and one that only dispatches never calls `init_flyte()`: its first `dispatch()` does.

### Sub-features

- **ROOT**: `from stargazer import Asset, Reference, assemble, fetch_bundle, init_flyte` works; `import stargazer` doesn't import marimo.
- **TPL-LOCAL**: the basic template, with no `init_flyte()` cell, stores an upload and runs its workflow "On this machine".
- **TUT**: the four tutorials run headless with the short imports.
- **CLUSTER**: a workspace notebook that never calls `init_flyte()` dispatches "On the cluster" and gets the run's output back.

### How to get to it (user POV)

Open the basic template or a tutorial from the dashboard, or locally with `marimo edit`; flip `run_location()` to "On the cluster".

### Driving it

Preconditions: the skill's Local notebook exports (`RUN_DIR`, the three `STARGAZER_*` paths, `PINATA_JWT=`). Run from `$RUN_DIR`, outside any git checkout, so no `.flyte/config.yaml` is found and `flyte.run` stays in-process.

1. ROOT: `pixi run pytest tests/unit/test_package_root.py tests/notebooks/test_ui.py`. Passes.
2. TUT: from `$RUN_DIR`, `pixi run --manifest-path $WT/pyproject.toml marimo export html $WT/src/stargazer/notebooks/tutorials/<nb>.py -o evidence/<nb>.html` for `assets`, `tasks`, `workflows`, `execution`. Exit 0 each. Execution needs matplotlib, which the dev env lacks: `uv pip install --python <pixi python> --target $RUN_DIR/pylib matplotlib`, then `PYTHONPATH=$RUN_DIR/pylib`. Its HTML shows `local CIDs == remote CIDs → True` and `Same CIDs as section 3 → True`.
3. TPL-LOCAL: from `$RUN_DIR`, `marimo run --headless --port 2731 $WT/src/stargazer/notebooks/templates/basic.py`, open it in the browser pane, upload a file (a synthetic `change` on the file input with a `DataTransfer` works), leave "On this machine". The upload cell shows a CID under `$RUN_DIR/store`, and the run table shows one row with that CID.
4. CLUSTER (devbox): a workspace notebook in `$RUN_DIR/workspace/` with a `.flyte/config.yaml` symlink to the checkout's, a header of `flyte`, `marimo`, `stargazer-bio`, an env on `notebook_image(__file__, "stargazer-probe")`, an `@app.function` task `double(x: int) -> int`, and `await dispatch(where, double, x=21)` with no `init_flyte()` anywhere. Serve it with `FLYTE_IMAGE_REGISTRY=localhost:30000 FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false` and `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open, click "On the cluster". The cell shows `probe result: 42 (remote)` and the server log the run's `SUCCEEDED`.

### Gotchas

- The template's workflow fetches its uploaded asset in the pod, and a kernel on this machine stores to its own disk, so the template itself can't be driven "On the cluster" on the devbox: that's what the probe notebook in step 4 stands in for.
- Storing before any init is the same as storing after: `init_from_config()` (devbox) and `init_in_cluster()` both leave Flyte's storage config `None`, so `flyte.storage` falls back to `S3.auto()` either way.

Run 2026-11-16 (`~/.stargazer/verify-runs/sdk-front-door-20261116-131842/evidence/`): ROOT 12 passed; TUT exit 0 ×4 with both `True`s; TPL-LOCAL CID `bafkreick6y2dfypenb5l37a55z5ds2gpbsuphj7br22hqnvvllwnmbbmqq` stored and returned in one row; CLUSTER devbox run `rv9hpcnbnzv7smglzbrx` SUCCEEDED, `42 (remote)`. Tasks tier 47 passed (30 gatk, 17 scrna). Not driven: the hosted notebook pod, which needs a debug image and a dashboard deploy.

Related: [[board]], [[bare-task-environments]], [[lean-task-bodies]], [[asset-find]].
