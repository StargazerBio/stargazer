---
title: retire-stargazer-login-project
status: done
priority: high
created: 2026-11-17
---

Infra PR 37 ([[ungated-login]]) moved the login app to the org's `admin` project, ungated. The tenant still holds what it replaced, and the next `./stargazer-users upgrade` deploys the new login app, which wants the `login` subdomain the old app in `stargazer` still holds. Union doesn't reject a second app asking for a taken subdomain; it hangs. So before the next `upgrade`, an org admin on the tenant:

- [x] Stops and deletes the old login app in the `stargazer` project
- [ ] Unassigns `stargazer-login` from every user, and deletes the policy
- [x] Archives the `stargazer` project
- [x] Runs `./stargazer-users upgrade`, which deploys the login app into `admin` and, with infra PR 38 ([[project-limits]]), gives every project its limits

Then check, as the test account in a fresh browser session, that the login address lands on its dashboard.

## Outcome

Done by hand on the tenant, 2026-11-17. Checked afterwards (measured): the `stargazer` project is archived; the login app runs in `admin` and the `u-pryce` dashboard runs on version `2026.11.16-99bb349`, infra main with PR 38; the login address, opened in a browser signed in as the test account, landed on `u-pryce`'s dashboard. Left: the `stargazer-login` policy still exists (`Policy.get` found it), so its assignments and the policy itself are still to delete. It binds viewer on an archived project, so it grants nothing that matters.

Related: [[board]], [[ungated-login]], [[project-limits]].
