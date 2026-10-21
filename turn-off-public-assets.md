---
title: A config that turns the public tier off in the dashboard
status: doing
priority: normal
created: 2026-10-20
---

Add a config that turns public assets off in the dashboard. Raised in the
merge comment on PR #58, alongside ticket `public-companion-curation`.
Today the public tier is on wherever `PINATA_JWT` is set, and on Union
it's injected into the dashboard and every pod (`STARGAZER_SECRETS`). The
only way to turn it off is to not have the key, which also turns off
publishing.

Decide first:

- **Whose config:** a per-user setting in the dashboard's Settings section
  (ticket `dashboard-settings`, then blocked by it), or a per-deployment
  one set when the dashboard is deployed (`stargazer-users`).
- **How far it reaches:** only the dashboard's Public tab, or the user's
  tasks and notebooks too, so `query()` and `fetch()`'s companion lookup
  never ask Pinata. The second means the launch passes it to each pod, the
  way `dashboard-settings` passes the save interval.
- **Publishing:** whether "off" also hides Publish, or only stops public
  assets from being listed and fetched.
