---
title: drop-notebook-asset
status: doing
priority: normal
created: 2026-11-16
---

Notebooks are published to the community repo, and the public tier holds none (ticket [[retire-public-notebooks]]), so the SDK's `Notebook` asset type has no use left. It goes: `src/stargazer/assets/notebook.py`, its export from `stargazer.assets` and from the package root (which PR 150, ticket [[sdk-front-door]], adds), the root test's list of types, `docs/architecture/types.md` and any other doc naming published notebooks as assets.

Waits on infra PR 33, which stops the dashboard importing the type, and on PR 150, which changes the same `__init__.py`. Infra's pin then moves to the release that drops it: infra's unit tier already passes with the type removed (RP-5 in the retire ticket).

Related: [[board]], [[retire-public-notebooks]], [[sdk-front-door]].
