---
title: old-header-sdk-source
status: review
priority: normal
created: 2026-11-09
pr: 143
---

A workspace notebook saved before the pixi sandbox points `stargazer-bio` at the image's SDK with `[tool.uv.sources]`, which pixi doesn't read. In the pixi sandbox it installs `stargazer-bio` from PyPI instead of `/stargazer`, so its kernel can run a different SDK from the image's (read from the header and the wiki's `marimo-sandbox` page; not driven). The launch already pins such a header's Python (ticket [[unpinned-notebook-python]]); the same step could move the source to `[tool.pixi.pypi-dependencies]`, or the dashboard could rewrite old headers on upgrade.

## Plan

On `fix/unpinned-notebook-python` beside the Python pin (PR 143), since it's the same launch step on the same unmerged branch.

- [x] `use_image_sdk()` in `runtime/proxy.py`, sharing `pin_python`'s header parsing: a header whose `[tool.uv.sources]` gives `stargazer-bio` a path gets the same path under `[tool.pixi.pypi-dependencies]`. A header pixi already sources, one with no uv source or a non-path one, and a missing file are left alone. Unit tests in `tests/unit/test_pin_python.py`.
- [x] `launch-notebook.sh` runs it after `pin_python`; `docs/architecture/runtime.md`.
- [x] The check in [[unpinned-notebook-python]]'s verification recipe (SDK), 2026-11-11: on the tenant, an old Blank notebook's kernel has `stargazer-bio` from `file:///stargazer` (measured); its evidence is in that ticket.

Related: [[board]], [[unpinned-notebook-python]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
