---
title: A build that failed with no page open is shown on the next visit
status: backlog
priority: normal
created: 2026-10-27
---

Since ticket `launch-build-state`, a launch whose image fails to build keeps its reason in the owner's state table, and `/launch/status` reports it as `failed` until the notebook is launched again. Only a tab already watching the build (`watchBuild` in `app/static/launch.js`) shows it, though. `hydrateLaunches` reads `running` and `building` on page load and ignores `failed`, so a build that fails while no dashboard page is open is never shown: the tile just offers Edit and Run again, and the next Edit builds again without saying why the last one failed.

Show a failed launch on load, on its tile rather than as an alert (several at once would stack), and clear it when the notebook is launched again.
