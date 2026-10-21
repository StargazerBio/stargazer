---
title: A config that turns the public tier off in the dashboard
status: done
priority: normal
created: 2026-10-20
pr: 73
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

## Decided (2026-10-21, best assumptions)

- **Whose config:** per deployment, `STARGAZER_PUBLIC_ASSETS=off` in the
  deployer's shell, forwarded into each dashboard by onboarding.
- **How far:** the dashboard only; tasks and notebooks keep the public tier.
- **Publishing:** off hides the public upload option and refuses the public
  routes, as having no Pinata key does.

## Outcome

Shipped in PR #73 (merge `0f43b8b`). `STARGAZER_PUBLIC_ASSETS=off` in the deployer's shell turns the dashboard's public tier off: onboarding forwards it, the public routes answer 503, and the page hides the public upload option and shows the Public tab's notice. Tasks and notebooks keep the public tier.

Verified with tests written first (unit tier 522 passed) and on Union with the test account's dashboard deployed from the branch: no public upload option, `?network=public` → 503 and `?network=private` → 200, with `PINATA_JWT` still in the pod's env. Torn down after. Nothing left; no comments on the PR.
