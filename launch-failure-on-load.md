---
title: launch-failure-on-load
status: done
priority: normal
created: 2026-10-27
pr: 8
---

Since ticket `launch-build-state`, a launch whose image fails to build keeps its reason in the owner's state table, and `/launch/status` reports it as `failed` until the notebook is launched again. Only a tab already watching the build (`watchBuild` in `app/static/launch.js`) shows it, though. `hydrateLaunches` reads `running` and `building` on page load and ignores `failed`, so a build that fails while no dashboard page is open is never shown: the tile just offers Edit and Run again, and the next Edit builds again without saying why the last one failed.

Show a failed launch on load, on its tile rather than as an alert (several at once would stack), and clear it when the notebook is launched again.

Done in the infra repo, StargazerBio/infra#8: the tile shows the reason on load and when a watched build fails, clamped and opened on click, and clears on the next launch of that mode.

## Outcome

Shipped in StargazerBio/infra#8 (merge `15f9195`): a failed launch shows its reason on its tile or card, on page load and when a watched build fails, clamped and opened on click, and clears when that mode is launched again. Verified locally with seeded rows and on the tenant with a build that failed while no page was open. Left: ticket `launch-row-on-delete`, a deleted notebook's launch rows staying in the state table. No follow-ups were left on the PR.
