---
title: images-repoint
status: backlog
priority: normal
created: 2026-11-21
---

Ticket [[split-config]] moved the image recipes from `stargazer.config` to `stargazer.images`. Two other repos still import a moved name from `stargazer.config` and break on the first release after `v2026.11.18.1`: infra's `app/dashboard.py` (`IMAGE_PLATFORM`), which lands with its `stargazer-bio` pin bump, and community-notebooks' `scrna/clustering-pipeline.py` (`notebook_image`). Each is a one-line repoint to `stargazer.images`, checked by importing the module against the new release.

Related: [[board]], [[split-config]], [[infra-sdk-pin-bump]].
