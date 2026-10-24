---
title: Pause and resume a user
status: backlog
priority: normal
created: 2026-10-24
---

`stargazer-users pause` and `resume` in infra. Pausing moves the user's login and their project key (`stargazer-<project>`) from `contributor` to `viewer` on their project and stops their apps. Viewer still passes the dashboard's login gate, so the user can look but not run anything. Resuming moves both back and redeploys their dashboard. From ticket `org-wide-platform-key`'s direction.
