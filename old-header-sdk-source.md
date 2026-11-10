---
title: old-header-sdk-source
status: backlog
priority: normal
created: 2026-11-09
---

A workspace notebook saved before the pixi sandbox points `stargazer-bio` at the image's SDK with `[tool.uv.sources]`, which pixi doesn't read. In the pixi sandbox it installs `stargazer-bio` from PyPI instead of `/stargazer`, so its kernel can run a different SDK from the image's (read from the header and the wiki's `marimo-sandbox` page; not driven). The launch already pins such a header's Python (ticket [[unpinned-notebook-python]]); the same step could move the source to `[tool.pixi.pypi-dependencies]`, or the dashboard could rewrite old headers on upgrade.

Related: [[board]], [[unpinned-notebook-python]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
