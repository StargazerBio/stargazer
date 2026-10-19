---
title: Index writes ride out a dashboard redeploy
status: backlog
priority: normal
created: 2026-10-19
blocked_by:
  - stale-dashboard-revisions
---

When a dashboard is redeployed, the new pod takes the index over from the old
one (ticket `stale-dashboard-revisions`). For about 15 s neither pod answers,
and index calls get 502s (13 s of them, measured on the tenant 2026-10-19).
`HttpIndex` retries 5xx with backoff, but its 5 attempts span about 7.5 s, so
a task or notebook write early in the pause fails. That's why
`refuse_while_running` makes `onboard` and `upgrade` wait for a user's runs
to finish.

Give `HttpIndex` enough attempts to span the pause with room to spare (7
attempts would span about 31 s), check it on the tenant by redeploying under
a steady stream of writes, then drop `refuse_while_running` and the retry
loop in `upgrade`.
