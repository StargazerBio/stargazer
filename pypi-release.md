---
title: Publish stargazer to PyPI
status: backlog
priority: normal
created: 2026-05-20
---

Once the package is published, notebook PEP 723 headers can pin a version (`stargazer == X.Y.Z`) instead of `[tool.uv.sources] stargazer = { path = "/stargazer", editable = true }`. Unlocks fully reproducible community notebooks without baking the source path.
