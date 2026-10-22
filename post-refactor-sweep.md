---
title: Cleanup sweep after the Oct 19–21 refactors
status: doing
priority: normal
created: 2026-10-22
---

PRs #51–#80 moved onboarding to the infra repo, the asset index to DSQL,
notebook pods to `main_env`, uploads to TUS and the devbox to `devbox/`. Fast
refactors leave debris behind. This sweep goes over every file they touched
for dead code, repeated logic, needlessly complicated code, redundant or wrong
docstrings, and docs that no longer match the code, then cleans it up on
`refactor/post-refactor-sweep`.
