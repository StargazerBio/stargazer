---
title: community-short-imports
status: backlog
priority: low
created: 2026-11-16
blocked_by:
  - sdk-front-door
---

The community notebooks move to the package root's imports (`from stargazer import Asset, assemble, fetch_bundle, ...`) and drop their own `init_flyte()` cell where they only dispatch, as the built-in ones do after ticket [[sdk-front-door]]. A PR in StargazerBio/community-notebooks, after a release carries PR 150, since the notebooks run on the SDK of the image they're opened in. Verify each "On this machine" through marimo's kernel, as [[community-kernel-headers]]' evidence did.

Related: [[board]], [[sdk-front-door]], [[community-kernel-headers]], [[catalog-at-main]].
