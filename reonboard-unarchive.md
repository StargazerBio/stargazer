---
title: Onboarding a returning user brings back their project and index
status: next
priority: high
created: 2026-10-27
---

Offboarding archives a user's project and keeps their asset index in its DSQL table. Onboarding them again doesn't find it: `_ensure_project` in infra's `stargazer_users/onboard.py` looks for the subject's project among active projects only. It creates `u-jane-2` instead, and `ensure_user_index` makes a new, empty `assets.u_jane_2`, leaving the user's rows in `assets.u_jane`, which nothing can log in to. Their notebooks come back, since the workspace store is keyed by subject; their assets' index rows don't.

Measured with infra's own test fakes: onboard, offboard, then onboard `jane@uni.edu` again wrote `project.create u-jane-2`, `policy.create stargazer-u-jane-2`, `key.create stargazer-u-jane-2` and `index.ensure u-jane-2`.

## Plan

- [ ] `_ensure_project` looks for the subject's project among archived projects too, and unarchives it (`Project.unarchive()`) rather than creating a new one. The rest of onboarding then recreates what offboarding removed: the policy assignment, the project key and its secret, and the index's IAM role and its mapping to the user's login. The table and login were kept, so the user's rows come back.
- [ ] Infra test: onboard, offboard, onboard gives the same project, its index ensured, and no `project.create`.
- [ ] Docs: `onboard.py`'s module docstring (returning users), infra's `AGENTS.md` Onboarding section, and stargazer's `docs/architecture/app.md` Onboarding section.

## Verification

- Infra's tests, with the new one failing before the change.
- Tenant: needs a second address to offboard and onboard again, since offboarding the test account takes down its dashboard (see ticket `self-serve-onboarding` on a second address). With one, upload an asset, offboard, onboard, and the dashboard lists it.
