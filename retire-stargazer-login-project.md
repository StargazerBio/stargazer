---
title: retire-stargazer-login-project
status: next
priority: high
created: 2026-11-17
---

Infra PR 37 ([[ungated-login]]) moved the login app to the org's `admin` project, ungated. The tenant still holds what it replaced, and the next `./stargazer-users upgrade` deploys the new login app, which wants the `login` subdomain the old app in `stargazer` still holds. Union doesn't reject a second app asking for a taken subdomain; it hangs. So before the next `upgrade`, an org admin on the tenant:

- [ ] Stops and deletes the old login app in the `stargazer` project
- [ ] Unassigns `stargazer-login` from every user, and deletes the policy
- [ ] Archives the `stargazer` project
- [ ] Runs `./stargazer-users upgrade`, which deploys the login app into `admin` and, with infra PR 38 ([[project-limits]]), gives every project its limits

Then check, as the test account in a fresh browser session, that the login address lands on its dashboard.

Related: [[board]], [[ungated-login]], [[project-limits]].
