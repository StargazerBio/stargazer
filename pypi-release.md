---
title: Publish stargazer to PyPI
status: maybe
priority: normal
created: 2026-05-20
blocked_by:
  - sdk-package
---

Once the package is published, notebook PEP 723 headers can pin a version (`stargazer == X.Y.Z`) instead of `[tool.uv.sources] stargazer = { path = "/stargazer", editable = true }`. Unlocks fully reproducible community notebooks without baking the source path.

Ticket `sdk-package` is the groundwork, and leaves open whether to publish to
PyPI, a private index or GitHub releases.
