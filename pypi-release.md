---
title: Publish the SDK to PyPI as stargazer-bio
status: maybe
priority: normal
created: 2026-05-20
blocked_by:
  - sdk-package
---

Once the package is published, notebook PEP 723 headers can pin a version (`stargazer-bio == X.Y.Z`) instead of `[tool.uv.sources] stargazer = { path = "/stargazer", editable = true }`. Unlocks fully reproducible community notebooks without baking the source path.

Ticket `sdk-package` is the groundwork. Decided 2026-10-26: PyPI, as the
distribution `stargazer-bio` (`stargazer` is taken there by an unrelated
package), importing as `stargazer`, with `0.x` versions and no compatibility
promise before 1.0.

Shelved with ticket `sdk-package` on 2026-10-27: the SDK runs from source
everywhere, so there is nothing to publish until an outside user needs to
pin versions. See its Shelved section.
