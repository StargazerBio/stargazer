---
title: ungated-login
status: doing
priority: normal
created: 2026-11-17
---

Every user can see a `stargazer` project next to their own, and it holds nothing but the login app (infra `app/login.py`). It exists because Union's app login only admits a visitor who can view the app's project, so onboarding gives every user `viewer` there (policy `stargazer-login`). The app doesn't need that login: it holds no key and acts only as the visitor. Take the login off (`requires_auth=False`), identify the visitor from their console session cookies, and serve it from the org's `admin` project, which no user gets a role on. Then onboarding stops making the project and policy, and the `stargazer` project is archived.

## Measured (2026-11-17, a throwaway ungated probe app in `admin`, opened as the test account)

- The console's `flyte_*` cookies reach an ungated app (`flyte_at_1`, `flyte_at_2`, `flyte_idt`, `flyte_rt`, `flyte_user_info`); no `X-User-*` headers do.
- With those cookies as `Cookie`, `ProjectService/ListProjects` answers 200 with the visitor's projects (`stargazer`, `u-pryce`), and `IdentityService/UserInfo` (flyteidl2 and flyteidl) answers 200 with their `subject`.
- Without cookies all three answer 401. Union's own gate sends such a visitor to `<console>/login?redirect_url=<app url>`.

## Pieces

- [ ] Login app: ungated, subject from `UserInfo` and projects from `ListProjects` with the session cookies, no session → the console's sign-in and back; served from `admin`
- [ ] Onboarding: no login project, policy or assignments
- [ ] Docs: `docs/architecture/app.md`, `app_internals.md`, onboarding docstring
- [ ] Verified on the tenant as the test account
- [ ] On the tenant after merge: stop the old login app, unassign and delete `stargazer-login`, archive `stargazer`, then `upgrade`

Related: [[board]], [[login-redirect]], [[login-starts-dashboard]]
