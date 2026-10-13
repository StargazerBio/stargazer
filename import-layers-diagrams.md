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
paths, it draws one diagram per path instead. Generated on demand, never
committed.

- [ ] Nested `ruff.toml` bans, `TID251` enabled in `pyproject.toml`
- [ ] `pydeps` dev dependency, `[tool.pydeps]` defaults, `cli/diagrams.sh`, `diagrams/` gitignored
- [ ] Docs: overview layering, contributing guide, `cli/README.md`, AGENTS.md
