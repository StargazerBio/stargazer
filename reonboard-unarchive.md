---
title: reonboard-unarchive
status: done
priority: high
created: 2026-10-27
pr: 3
---

Offboarding archives a user's project and keeps their asset index in its DSQL table. Onboarding them again doesn't find it: `_ensure_project` in infra's `stargazer_users/onboard.py` looks for the subject's project among active projects only. It creates `u-jane-2` instead, and `ensure_user_index` makes a new, empty `assets.u_jane_2`, leaving the user's rows in `assets.u_jane`, which nothing can log in to. Their notebooks come back, since the workspace store is keyed by subject; their assets' index rows don't.

Measured with infra's own test fakes: onboard, offboard, then onboard `jane@uni.edu` again wrote `project.create u-jane-2`, `policy.create stargazer-u-jane-2`, `key.create stargazer-u-jane-2` and `index.ensure u-jane-2`.

## Plan

- [x] `_ensure_project` looks for the subject's project among archived projects too, and unarchives it (`Project.unarchive()`) rather than creating a new one. The rest of onboarding then recreates what offboarding removed: the policy assignment, the project key and its secret, and the index's IAM role and its mapping to the user's login. The table and login were kept, so the user's rows come back.
- [x] Infra test: onboard, offboard, onboard gives the same project, its index ensured, and no `project.create`.
- [x] Docs: `onboard.py`'s module docstring (returning users) and infra's `AGENTS.md` Onboarding section.
- [x] ~~Stargazer's `docs/architecture/app.md`~~: dropped, since ticket [[split-app-repo]] moves the app docs to infra, whose `AGENTS.md` and `onboard.py` already say it.

## Verification

- Infra's tests, with the new one failing before the change.
- Tenant: needs a second address to offboard and onboard again, since offboarding the test account takes down its dashboard (see ticket [[self-serve-onboarding]] on a second address). With one, upload an asset, offboard, onboard, and the dashboard lists it.

Infra PR is StargazerBio/infra#3. Measured on the tenant: `Project.unarchive()` as the org admin brings an archived project back to active with its labels (round trip on `u-387300641116005877`, archived again after). Not measured: whether DSQL accepts a login from an IAM role deleted and recreated under the same ARN; onboarding skips `AWS IAM GRANT` when the mapping row's ARN matches. The second-address run settles it.

## Outcome

Shipped in StargazerBio/infra#3 (merge `f16194d`). `_ensure_project` unarchives the archived project labeled with the returning user's subject instead of creating `u-<handle>-2`. The rest of onboarding remakes the assignment, the project key and its secret, and the index's IAM role. Verified with infra's test `test_returning_user_gets_their_archived_project_back`, which failed before the change. On the tenant, `Project.unarchive()` was round-tripped as the org admin (measured). Left: the full offboard-and-onboard run on the tenant, including whether DSQL accepts the recreated IAM role, in ticket [[reonboard-tenant-check]].
