---
title: sdk-front-door
status: next
priority: high
created: 2026-11-16
---

A researcher's notebook should import what it needs from `stargazer`, and its setup block should hold only what they'd change. From an architectural scan of `main` (2026-11-16):

- `src/stargazer/__init__.py` exports `PinataClient`, `StorageClient`, `default_client` and `get_client`, which a notebook never touches, and none of what one does. The built-in and community notebooks import from eight submodules (measured, `grep` over their `from stargazer…` lines): `assets.asset`, `assets.scrna`, `assets.reference`, `config`, `notebooks`, `notebooks.ui`, `bundles`, `tasks.scrna.env`.
- Every notebook calls `init_flyte()` in its first cell (6 of 6 that dispatch).
- `templates/basic.py`'s setup block imports `STARGAZER_ENV_VARS`, `STARGAZER_SECRETS`, `notebook_image` and `notebook_env` before any of the user's own code. PR 149 (ticket [[bare-task-environments]]) drops the env vars; this ticket starts from what it leaves.

## Plan

- [ ] `stargazer/__init__.py` exports `Asset`, `assemble`, `fetch_bundle`, `init_flyte` and the asset types; the storage clients stay importable from `stargazer.utils`. Check the import layers (`src/stargazer/ruff.toml`) allow it, and that infra's imports of the old names still resolve or are changed in the same pin bump.
- [ ] `dispatch` and `run_location` import marimo, which the core doesn't depend on, so they can't be imported eagerly at the root. Settle: leave them at `stargazer.notebooks.ui`, or expose them through a module `__getattr__`.
- [ ] `dispatch` initializes Flyte on first use when nothing has, so a notebook doesn't call `init_flyte()` itself. It stays public for SDK users.
- [ ] The templates, tutorials and `runtime/notebook_agent.md` use the short imports. The community notebooks follow in their own repo.
- [ ] Docs: the guides' examples, `docs/architecture/notebook.md`.

Verify by opening the basic template from the image, hosted and locally, and running its workflow both ways.

Related: [[board]], [[bare-task-environments]], [[lean-task-bodies]], [[asset-find]].
