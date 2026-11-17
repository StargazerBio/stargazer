---
title: catalog-at-main
status: review
priority: normal
created: 2026-11-16
pr: 7
---

The community repo pins nothing about a notebook (no locks, no image digests: it runs on the SDK of the image it's opened in), except that `catalog.yaml` pins each featured notebook to a commit. The two pull against each other: a pinned notebook stays as it was while the SDK under it moves.

Seen 2026-11-16 (measured, `git show` on `origin/main` of community-notebooks): the catalog pins both notebooks at `63e5c101`, where `scrna/clustering-pipeline.py` imports `scrna_env` from `stargazer.config` and asks for `stargazer-bio[bio]`. Neither exists on stargazer `main`. The fix merged as PR 5 (`002bc8e`, ticket [[community-kernel-headers]]) and the pins haven't moved, so Featured still serves the old file. That it fails on an image built from `main` is inferred, not driven.

The idea: the catalog lists paths, and Featured is those paths at `main`. What keeps a featured notebook working is a check, not a pin: the repo's CI imports each notebook against the latest release (and could run the demo inputs).

What would go in infra: reading each pinned file from the archive or its raw URL at a commit, and the split between a Featured listing at pins and a Community one at `main` (`app/community_listing.py`); a catalog entry becomes a flag on a notebook in one listing.

To settle: the pin is also the review record ("the commit its maintainers reviewed"). Whether a notebook changing under Featured without a second look is acceptable in a repo with no review on publish.

For the MVP, the least it takes is moving the pins to a commit that runs on the release; the redesign can wait.

## MVP: pins moved (2026-11-17)

StargazerBio/community-notebooks PR 7, branch `fix/catalog-at-main`: both pins move to `a58cdfc` (PR 6's merge). Measured with the dashboard's own path: at `63e5c10` the scRNA notebook is missing `stargazer.config.scrna_env` on `stargazer-bio==2026.11.16`, and at `a58cdfc` both notebooks' imports resolve; infra's `community_listing.listing()` with the new catalog lists both as Featured from their raw files. The redesign above (Featured at `main`, kept working by CI) stays open: at merge it becomes its own `maybe` ticket.

Related: [[board]], [[community-kernel-headers]], [[retire-public-notebooks]].
