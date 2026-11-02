---
title: post-refactor-sweep
status: done
priority: normal
created: 2026-10-22
pr: 81
---

PRs #51–#80 moved onboarding to the infra repo, the asset index to DSQL,
notebook pods to `main_env`, uploads to TUS and the devbox to `devbox/`. Fast
refactors leave debris behind. This sweep goes over every file they touched
for dead code, repeated logic, needlessly complicated code, redundant or wrong
docstrings, and docs that no longer match the code, then cleans it up on
`refactor/post-refactor-sweep`.

## Progress

Seven review passes (dashboard core, asset routes and identity, notebook
pods and deploy, SDK storage, SDK notebooks, tests, docs) found about 280
issues. The fixes are four commits on the branch, net about 700 lines lighter:

- [x] Storage tier and asset routes. Fixes two bugs: a public edit from the
  dashboard could hand the record to the dashboard's owner, and deleting a
  bundle-fetched CID raised. Also one copy of each shape and stale dependencies
  dropped.
- [x] SDK notebooks and qc_filter: prose matched to the code, QC histograms
  using the task's gene prefixes.
- [x] App tier: shared helpers, docstrings that match the code. The asset
  browser compares records with the visitor, not the owner an admin stands in for.
- [x] Docs: stale claims fixed, history and measurements out of durable docs,
  one owner per explanation. Gaps went to tickets [[long-image-build-launch]]
  and [[public-surface-rate-limit]].

Verification: unit tier 485 passed and every pre-commit hook passed. Pinata
tier 11 passed against the real API. The scRNA tasks tier passed 18 in its
image. A local stand-in dashboard was driven in Chrome: create, setup save,
copy, settings, delete, a private resumable upload, tabs, list view and a
metadata edit all worked. On Union, the test account's dashboard deployed from
the branch with the expected env and listed its 64 DSQL assets. A Basic
notebook launch then hung: the redeployed dashboard pod has no
`EAGER_API_KEY` (measured), so its in-pod image build waited on a browser
sign-in until Cloudflare returned a 504. That's ticket [[org-wide-platform-key]],
not this branch. The test notebook "Sweep 1022" is left in the test account's
workspace. Everything was torn down: dashboard stopped, no live runs.

## Outcome

Shipped in PR #81 (merge `01681e1`): four commits over the files #51–#80 touched, about 700 lines lighter, fixing two bugs (a public edit from a dashboard restamped the record's owner, and deleting a bundle-fetched CID raised) and the asset browser's owner comparison.

Verified with the unit tier (485), the Pinata tier (11) against the real API, the scRNA tasks tier (18), a local dashboard driven in Chrome, and on Union with the test account: the dashboard deployed from the branch with the expected env and listed its 64 DSQL assets. No comments on the PR.

Left: a notebook launch on Union wasn't verified (ticket [[org-wide-platform-key]]), and the test notebook "Sweep 1022" is still in the test account's workspace. The gaps the sweep found are tickets [[long-image-build-launch]] and [[public-surface-rate-limit]].

Related: [[board]].
