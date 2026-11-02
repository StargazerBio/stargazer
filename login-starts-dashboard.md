---
title: login-starts-dashboard
status: done
priority: normal
created: 2026-10-31
pr: 28
---

A user whose dashboard is stopped who signs in through `stargazer.bio/login` lands on a bare 404. A stopped (deactivated) app has no route, so Union's ingress answers for it and none of Stargazer's code runs. An idle dashboard that has only scaled to zero still reports `DEPLOYMENT_STATUS_ACTIVE` and wakes on request (measured on the tenant: the login app, idle). So only a deactivated one 404s. `stargazer-users pause` deactivates dashboards, and so does test teardown.

The login app is the one place a stopped dashboard can be caught: it already knows the visitor's project and calls Union as the visitor. Before it redirects, it reads the dashboard's app record with the visitor's token:

- Desired state not `STOPPED` and status active: the "Opening your workspace" page, as now.
- Desired state `STOPPED`: start it as the visitor (`AppService/Update`, desired state `STARTED`) and show "Starting your workspace", which refreshes back to `/` until it's active.
- Started but not active yet: the same starting page.
- Union refuses the start: the visitor is a `viewer`, so the workspace is paused. A "Workspace paused" page says to contact the admin, pryce@stargazer.bio.

Pause stays enforced by Union's RBAC, and the login app still holds no key. A bookmarked dashboard address still gets Union's 404, since nothing of ours runs there.

Work in StargazerBio/infra#28 (`fix/login-starts-dashboard`). The app service refuses the visitor's ID token (`Identity: <nil>`), so `Get` and `Update` forward the visitor's `flyte_*` console session cookies, which do work (measured).

## Verification recipe

On the tenant as the test account, with the branch's login app served as a copy under its own name and subdomain in `stargazer` (so the live login app is untouched):

1. Stop the test account's dashboard: `flyte --config .flyte/union.yaml update app dashboard --deactivate -p u-pryce -d development --wait`. Its address answers 404 to `curl`.
2. Open the copy in the browser. It shows "Starting your workspace" and refreshes; the dashboard's desired state turns `STARTED`. Once active, the page moves on and the dashboard renders.
3. Stop the dashboard again, and pause: remove the test account's `contributor` binding (`stargazer-users pause --email pryce@stargazer.bio`). Open the copy: "Workspace paused" with the admin's address, and the dashboard stays stopped. `resume` it afterwards.
4. Stop the copy and the dashboard.

## Verification (2026-10-31, branch at `02e27c7`)

All on the tenant, as the test account, through a `login-test` copy that has since been deleted. The stopped dashboard (404) turned `STARTED` from the visit, and its address answered 10 s later. The starting page then moved on to the rendered dashboard by itself. Paused, the visit showed "Workspace paused" with pryce@stargazer.bio, and the dashboard stayed `STOPPED`. Resumed and running, the visit went straight to the dashboard.

## Outcome

Shipped in StargazerBio/infra#28 (merged 2026-10-31). The login app reads the visitor's dashboard record with their `flyte_*` session cookies and starts a stopped dashboard, waiting on a starting page. For a paused user it shows a "Workspace paused" page with pryce@stargazer.bio. It was verified on the tenant through a `login-test` copy (above).

Left: the live login app runs this only once it's redeployed from `main` (`deploy_login`, or a bare `stargazer-users upgrade`). A bookmarked dashboard address still gets Union's 404.

Related: [[launch-wait-route]], [[login-redirect]], [[flyte-apps]], [[board]].
