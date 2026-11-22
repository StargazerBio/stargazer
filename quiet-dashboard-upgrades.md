---
title: quiet-dashboard-upgrades
status: later
priority: normal
created: 2026-11-22
---

`stargazer-users upgrade` runs from an admin's machine and redeploys every dashboard at once, so a user signed in at that moment loses their dashboard mid-use. As users grow, upgrades should roll out on their own, each dashboard redeployed when it's both behind the pinned release and quiet.

## Approach

A scheduled task (a Flyte trigger on a cron) in the org's `admin` project, which no user has a role on and which has no inbound address. Every N minutes it lists the Stargazer projects, compares each dashboard's deployed version with the pinned release, and runs `_upgrade_project` on the ones that are behind and quiet. It's `upgrade_all` with a filter, and nothing runs between ticks.

Not on the login app: it is public and unauthenticated (`requires_auth=False`), holds no key by design, and makes every call as the visitor. Upgrading needs org-admin Union rights (`_ensure_project_key` creates API keys and policies) and admin AWS rights (`ensure_user_role` creates IAM roles, `ensure_user_index` creates DSQL logins), and the login app scales to zero after an hour like a dashboard. A loop in any app's web process would also run once per replica and restart whenever Knative rescales it.

## Open questions

- **What "quiet" reads as.** A dashboard scales to zero after an hour with no requests (`Scaling(replicas=(0, 1), scaledown_after=1h)`), so scaled to zero means an hour unused. Unchecked: whether Union's app status tells scaled-to-zero apart from running (the login app reads only `DEPLOYMENT_STATUS_ACTIVE`/`STARTED`), and whether redeploying an app at zero brings a pod up.
- **Credentials.** An org-admin API key as a secret in `admin` (`onboard.py` already runs under `FLYTE_API_KEY`), and an AWS role for the task's pods with the IAM and DSQL rights, made with tofu.
- **What the task ships.** `deploy_dashboard` bundles the deployer's loaded modules, so the task's image holds the infra code, and `release_version()` reads `git describe` of a checkout, which a pod hasn't got, so the version is baked in.
- **Splitting the privileged steps.** The key, IAM role and index rarely change between releases. A loop that only redeploys dashboards could run on a narrower credential, with the ensure steps left to `upgrade` when a release needs them. Keep them together until the key's reach is a concern.
- **The login app.** `upgrade` redeploys it too; it scales to zero, so the same quiet check applies.

Related: [[board]], [[small-node-pool]], [[login-starts-dashboard]], [[pause-resume-users]].
