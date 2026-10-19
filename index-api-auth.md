---
title: The dashboard's index API takes no credential
status: backlog
priority: normal
created: 2026-10-18
blocked_by:
  - org-wide-platform-key
---

The dashboard serves its owner's asset index at `/index/*`, and tasks and
notebook pods call it at the dashboard's in-cluster address with no token
(`stargazer.utils.index.HttpIndex`). That address skips Union's login, and
any pod in any project can reach it (measured 2026-10-18, ticket
`internal-address-auth`), so any pod can read, add to, rewrite or delete
rows in any user's index. `internal-address-auth` closed the dashboard's
user routes and the notebook pods; this is what's left.

## Direction

A per-dashboard index credential:
- onboarding mints a random token for each dashboard
- the dashboard hands it to its notebook pods at launch
- `stargazer.config._stargazer_env_vars()` forwards it into the runs they
  start
- `HttpIndex` sends it with every call, and `/index/*` refuses a call
  without it

Blocked by `org-wide-platform-key`: while every pod carries the org's
platform key, which can read every app's spec and run tasks in any project,
a token in an app's spec or a run's env reaches anyone anyway. The bucket is
shared too (`per-user-storage-isolation`), so the rows' files are readable
regardless.
