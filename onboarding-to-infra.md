---
title: onboarding-to-infra
status: done
priority: high
created: 2026-10-21
pr: 76
---

Onboarding (`stargazer-users`: invite, project, access policy, `upgrade`, `offboard`) moves out of stargazer into the `StargazerBio/infra` repo, as the same Python, so every AWS operation the org admin runs lives in one place (decided 2026-10-21, when per-user DSQL setup started adding IAM and DSQL admin calls to onboarding). Infra depends on the sibling stargazer checkout and deploys from its `main`.

What stays in stargazer is what deploys a dashboard, since the devbox (which stays here) and the `verify-stargazer` script use it: `deploy_dashboard`, `build_notebook_image`, `release_version`, `active_runs`, `refuse_while_running` and `stop_project_apps`, in `app/deploy.py`.

## Pieces

- [x] stargazer: `app/deploy.py` from `app/onboard.py`'s deploy half; `app/onboard.py`, its tests, the `stargazer-users` script and the `flyteplugins-union` dependency go; consumers and docs follow
- [x] infra: the user/project/access half, `upgrade`, `offboard` and the CLI, with their tests, depending on `../stargazer`
- [x] Verify: the unit tiers of both repos, and `stargazer-users` from infra redeploys the test account's dashboard from stargazer

The per-user DSQL setup from ticket [[dsql-asset-index]] lands in infra after this.

## Verification (2026-10-21)

- stargazer, branch `refactor/onboarding-to-infra` (`fc74634`): unit tier 531 passed (the 20 onboarding tests moved out; the 9 deploy tests are `tests/unit/test_deploy.py`).
- infra, branch `feat/onboarding` (`515c82b`, local, unmerged): its 20 onboarding tests pass against the stargazer branch on `PYTHONPATH`. The fake control plane also patches `app.deploy.active_runs`; without it ten tests reached a real, uninitialized Flyte client.
- Real surface: `stargazer-users onboard --email pryce@stargazer.bio` from infra, against the branch. It found the existing user and project (no invite, no create), built `notebook-app-3921aa04…`, and deployed `dashboard` in `u-pryce` at version `69f99a2` (the branch before a wording-only amend): `DEPLOYMENT_STATUS_ACTIVE`, `STARGAZER_VERSION=69f99a2`, public URL 302 to Union's login. Then deactivated: `DESIRED_STATE_STOPPED`, no active apps in `u-pryce`, no running runs.
- Order: infra's `main` imports `app.deploy`, so `feat/onboarding` merges there only after stargazer's PR merges.

## Outcome

Shipped in PR #76 (merge `d92ce15`): stargazer keeps `app/deploy.py`, and onboarding (`stargazer-users`) lives in infra's `stargazer_users/`, merged into infra's local `main` (`515c82b`), depending on `../stargazer` editable. Verified as above, and again after the merge: infra imports `app.deploy` from stargazer's `main` with no override, its 20 tests pass, and `stargazer-users --help` lists `onboard`, `upgrade` and `offboard`. No comments on the PR. Next: the per-user DSQL setup lands in infra, on ticket [[dsql-asset-index]].

Related: [[board]].
