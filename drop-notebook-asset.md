---
title: drop-notebook-asset
status: done
priority: normal
created: 2026-11-16
pr: 155
---

Notebooks are published to the community repo, and the public tier holds none (ticket [[retire-public-notebooks]]), so the SDK's `Notebook` asset type has no use left. It goes: `src/stargazer/assets/notebook.py`, its export from `stargazer.assets` and from the package root (which PR 150, ticket [[sdk-front-door]], adds), the root test's list of types, `docs/architecture/types.md` and any other doc naming published notebooks as assets.

Waits on infra PR 33, which stops the dashboard importing the type, and on PR 150, which changes the same `__init__.py`. Infra's pin then moves to the release that drops it: infra's unit tier already passes with the type removed (RP-5 in the retire ticket).

## Evidence (2026-11-16)

PR 155, `refactor/drop-notebook-asset`.

- Unit tier 319 passed; notebook smoke 23 passed; `zensical build --clean` no issues.
- Stored `asset=notebook` records after removal (scratch script, real `StorageClient` + SQLite index): `specialize`, `build_asset` and `assemble(asset="notebook")` all return a bare `Asset` with the keyvalues verbatim. Nothing raises.
- Infra main `43c7c5c`: no `Notebook` import from stargazer; explorer `asset=notebook` entries are dicts from `notebook_keyvalues`, never through the SDK registry. RP-5 on the pinned 2026.10.30: 388 passed (3 runs).
- Infra unit tier against this branch's SDK: errors at setup on branch and `origin/main` alike (infra conftest patches `storage.default_client`, gone on main). With an alias shim: 387 passed, 1 failed, identical on both (`test_basic_template_declares_an_environment_on_notebook_base`, template drift).
- Infra at its pin bump: drop the dead `NOTEBOOK_KEY` skip in `/assets/schema`; fix the `default_client` fixture and the basic-template test, both unrelated drift.

## Outcome

Shipped in PR 155 (merge `91c1248`): the `Notebook` asset type and its exports are gone, and stored `asset=notebook` records read back as a bare `Asset`. Verified as under Evidence: unit tier 319 passed, notebook smoke 23 passed, the docs build clean. Left: at infra's next pin bump, drop the dead `NOTEBOOK_KEY` skip in `/assets/schema` and fix the `default_client` fixture and the basic-template test. No review comments.

Related: [[board]], [[retire-public-notebooks]], [[sdk-front-door]].
