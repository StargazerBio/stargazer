---
title: images-repoint
status: doing
priority: normal
created: 2026-11-21
---

Ticket [[split-config]] moved the image recipes from `stargazer.config` to `stargazer.images`. Two other repos still import a moved name from `stargazer.config` and break on the first release after `v2026.11.18.1`: infra's `app/dashboard.py` (`IMAGE_PLATFORM`), which lands with its `stargazer-bio` pin bump, and community-notebooks' `scrna/clustering-pipeline.py` (`notebook_image`). Each is a one-line repoint to `stargazer.images`, checked by importing the module against the new release.

## Plan

- [x] A release carrying the move: stargazer PR 173 sets `version` to `2026.11.22`, which releases on merge.
- [x] infra `fix/images-repoint` (pushed, no PR yet): `IMAGE_PLATFORM` from `stargazer.images`, and the dead `NOTEBOOK_KEY` skip in `/assets/schema` dropped (the SDK has registered no `notebook` since `v2026.11.18`). Pinned to stargazer `main`'s archive (`3eb9de6`) for now: the unit tier failed to collect before the repoint and passed after, 447 tests (measured 2026-11-22).
- [x] community-notebooks `fix/images-repoint` (pushed, no PR yet): the scRNA pipeline takes `notebook_image` from `stargazer.images` (`7da2ad2`), and the catalog's scRNA entry moves to that commit. Against stargazer `main`, the notebook failed to import before the change and imported after; the germline notebook imports too (measured 2026-11-22).
- [ ] Once 2026.11.22 is on PyPI: infra pins `stargazer-bio==2026.11.22` (`uv lock`), reruns its unit tier and checks the test account's dashboard on the tenant, then opens its PR. The community-notebooks PR opens beside it, after a reimport against the published package, and merges only after the dashboards run 2026.11.22, since its catalog entry no longer imports on 2026.11.18.1.

Related: [[board]], [[split-config]], [[infra-sdk-pin-bump]].
