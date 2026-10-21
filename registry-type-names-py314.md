---
title: The registry renders optional types as Union[...] on Python 3.14
status: review
priority: low
created: 2026-10-20
pr: 65
---

`_type_name` in `src/stargazer/registry.py` renders `X | None` as
`X | NoneType` on Python 3.13, where the hint is a `types.UnionType` with no
`__origin__`. On 3.14 the same hint has `__origin__ = typing.Union`, so it
takes the generic branch and renders `Union[X, NoneType]`. Measured
2026-10-20: `docs/gen_catalog.py` run from a 3.14.7 venv rewrote four rows of
`docs/reference/catalog.md` (`apply_vqsr`, `bwa_mem`, `bwa_mem2_mem`,
`joint_call_gvcfs`) that a 3.13.4 venv leaves unchanged.

`uv` picks 3.14 for a fresh worktree venv when it is installed
(`requires-python = ">=3.13"`), so the catalog hook flips those rows depending
on who commits. The task images are built on a py3.14 base, so the MCP
`list_tasks` descriptions served from one would read `Union[...]` too
(inferred, not checked). Render unions the same way on both versions, and
consider pinning the dev Python in `.python-version`.

Found while working on ticket `qc-filter-organism-from-asset`.
