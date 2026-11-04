---
title: drop-notebook-extra
status: doing
priority: normal
created: 2026-11-04
---

The SDK's `pyproject.toml` declares no notebook-specific dependencies: no notebook is special. A notebook names what it needs in its own header (the SDK, `stargazer-bio[bio]` for scRNA in its own process, and with [[pixi-notebook-sandbox]] its tools), or adds it ad hoc. The `notebook` extra (`marimo` plus `bio`) and its place in `all` go. Nothing but the dev venv used it: no image, no infra code, no community notebook (measured by grep, 2026-11-04). marimo moves to the `dev` group, for the unit tier's notebook tests and `marimo edit` from a checkout; a notebook kernel always has it, so `stargazer.notebooks.ui` needs no declaration.

Related: [[board]], [[pixi-notebook-sandbox]], [[pixi-dependencies]].
