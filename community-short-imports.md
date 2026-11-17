---
title: community-short-imports
status: done
priority: low
created: 2026-11-16
pr: 6
---

The community notebooks move to the package root's imports (`from stargazer import Asset, assemble, fetch_bundle, ...`) and drop their own `init_flyte()` cell where they only dispatch, as the built-in ones do after ticket [[sdk-front-door]]. A PR in StargazerBio/community-notebooks, after a release carries PR 150, since the notebooks run on the SDK of the image they're opened in. Verify each "On this machine" through marimo's kernel, as [[community-kernel-headers]]' evidence did.

PR 6 in StargazerBio/community-notebooks. Both notebooks ran through marimo's kernel in their headers' pixi environments on the released `stargazer-bio==2026.11.16`, empty store, "On this machine": scRNA stored all six stages for `s1d1` (6307 cells) and `s1d3` (7157); germline with `--run` stored a 47-record cohort VCF (measured).

## Outcome

Shipped in StargazerBio/community-notebooks PR 6 (merge `a58cdfc`): both notebooks import from the package root and dispatch without their own Flyte init. Verified through marimo's kernel on `stargazer-bio==2026.11.16`, as above. Nothing left. No review comments.

Related: [[board]], [[sdk-front-door]], [[community-kernel-headers]], [[catalog-at-main]].
