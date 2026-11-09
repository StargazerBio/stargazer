---
title: unpinned-notebook-python
status: backlog
priority: high
created: 2026-11-09
---

A notebook whose header doesn't pin Python under `[tool.pixi.dependencies]` gets Python 3.15 in the pixi sandbox, and its kernel never starts: marimo's runtime overlay (`pixi exec --spec uv>=0.12 uv run --no-project --python <env python> --with marimo==0.25.1`) finds no cp315 wheel for `loro`, which marimo depends on, builds its sdist, and PyO3 refuses 3.15 ("newer than PyO3's maximum supported version (3.14)"). The editor sits on "Starting kernel…" with no error in the notebook.

Measured on the tenant on 2026-11-09, as the test account, with a notebook image built from `main` plus run-modes (`ghcr.io/stargazerbio/debug:run-modes`): a workspace notebook created from the dashboard's Blank seed hit it. The dashboard pins release 2026.10.30, whose `templates/blank.py` header is uv-style (`requires-python = ">=3.14"`, `[tool.uv.sources]`) with no pixi Python pin. The same notebook's kernel starts on the 2026.10.30 image, which predates the pixi sandbox, and a built-in notebook from `main` (pinning `python = "3.14.*"`) starts on the new image.

So every workspace notebook saved before the pixi sandbox, and any community notebook without the pin, breaks once the dashboard moves to a release with the pixi sandbox. Options to weigh: the launch pins Python when a header doesn't (an overlay constraint or a default `python` dependency), or the dashboard rewrites old headers on upgrade. Verify by creating a notebook from an old seed on the new image and seeing its kernel start.

Related: [[board]], [[pixi-notebook-sandbox]], [[run-modes]], [[marimo-sandbox]].
