---
title: featured-follows-main
status: maybe
priority: low
created: 2026-11-17
---

`catalog.yaml` in the community repo pins each featured notebook to a commit, while the notebook runs on the SDK of the image it's opened in. The two pull against each other: a pinned notebook stays as it was while the SDK under it moves, so every release that changes an API a featured notebook uses leaves Featured broken until someone moves the pins by hand ([[catalog-at-main]] did it once).

The idea: the catalog lists paths, and Featured is those paths at `main`. What keeps a featured notebook working is a check, not a pin: the repo's CI imports each notebook against the latest release (and could run the demo inputs).

What would go in infra: the split between a Featured listing at pins and a Community one at `main` (`app/community_listing.py`) goes, and a catalog entry becomes a flag on a notebook in the one listing at `main`.

To settle: the pin is also the review record ("the commit its maintainers reviewed"). Whether a notebook changing under Featured without a second look is acceptable in a repo with no review on publish.

Related: [[board]], [[catalog-at-main]], [[community-kernel-headers]].
