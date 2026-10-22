---
title: Onboarding moves to the infra repo
status: doing
priority: high
created: 2026-10-21
---

Onboarding (`stargazer-users`: invite, project, access policy, `upgrade`, `offboard`) moves out of stargazer into the private `StargazerBio/infra` repo, as the same Python, so every AWS operation the org admin runs lives in one place (decided 2026-10-21, when per-user DSQL setup started adding IAM and DSQL admin calls to onboarding). Infra depends on the sibling stargazer checkout and deploys from its `main`.

What stays in stargazer is what deploys a dashboard, since the devbox (which stays here) and the `verify-stargazer` script use it: `deploy_dashboard`, `build_notebook_image`, `release_version`, `active_runs`, `refuse_while_running` and `stop_project_apps`, in `app/deploy.py`.

## Pieces

- [ ] stargazer: `app/deploy.py` from `app/onboard.py`'s deploy half; `app/onboard.py`, its tests, the `stargazer-users` script and the `flyteplugins-union` dependency go; consumers and docs follow
- [ ] infra: the user/project/access half, `upgrade`, `offboard` and the CLI, with their tests, depending on `../stargazer`
- [ ] Verify: the unit tiers of both repos, and `stargazer-users upgrade` from infra redeploys the test account's dashboard from stargazer's `main`

The per-user DSQL setup from ticket `dsql-asset-index` lands in infra after this.
