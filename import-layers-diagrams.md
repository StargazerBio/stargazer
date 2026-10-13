---
title: Import layer rules and on-demand import diagrams
status: doing
priority: normal
created: 2026-10-13
---

Two ways to see and keep the shape of the code, so its code paths are easier
to follow.

**Layer rules in ruff.** The layering in `docs/architecture/overview.md` is
only a picture today; nothing stops a task importing a workflow. Enforce it
with ruff's banned-api rule (`TID251`), scoped per directory with nested
`ruff.toml` files. Layers, bottom up: storage (`assets`, `utils`), `tasks`,
`workflows`, the surfaces (`registry`, `server`, `notebooks`), then `app/`.
Each directory bans every layer above its own. Ruff only checks direct
imports, so the bans go in every lower directory, which also rules out an
indirect path through a module in between.

**pydeps diagrams.** `cli/diagrams.sh` draws import graphs into a gitignored
`diagrams/`: the SDK by package, the SDK by module, and the app tier. Given
module files, it draws each with everything it imports instead. Generated on demand, never
committed.

- [x] Nested `ruff.toml` bans, `TID251` enabled in `pyproject.toml`
- [x] `pydeps` dev dependency, `[tool.pydeps]` defaults, `cli/diagrams.sh`, `diagrams/` gitignored
- [x] Docs: overview layering, contributing guide, `cli/README.md`, AGENTS.md

## Verification

- Before: forbidden imports planted at each layer boundary got only F401 from
  ruff. After: each fails with TID251, including an import inside a function
  in `tasks/gatk/`; a notebook importing a workflow (allowed) still passes.
  The pre-commit ruff hook rejects a planted task-imports-workflow file.
- `ruff check` and `ruff format --check` output is identical to before over
  the whole repo, and `--show-settings` for files under the nested configs
  differs only in TID251 and the ban lists.
- `ruff analyze graph`: 0 layer violations, indirect paths included.
- `cli/diagrams.sh`: sdk.svg 11 packages, sdk-modules.svg 55 modules, app.svg
  29 nodes incl. the SDK modules app/ reaches; per-module runs include the
  module's own node and everything it reaches.

Known gap: the modules at the package root (`config`, `marshal`) and
`bundles/` are only held to staying out of `app/`, since `registry` and
`server` share their directory and banned-api can't be scoped per file.
