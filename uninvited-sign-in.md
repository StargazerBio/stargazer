---
title: uninvited-sign-in
status: maybe
priority: normal
created: 2026-10-30
---

A visitor without an invite who clicks Log in on stargazer.bio gets stuck at Union's sign-in. They never reach anything Stargazer controls. `stargazer.bio/login` forwards to the login app (infra `app/login.py`). That app is `requires_auth=True`, so Union's gate runs first:

- **No Union account.** Union's sign-in offers Google, GitHub and Microsoft (measured). Union doesn't create a user on first sign-in (ticket `self-serve-onboarding`), so I expect Union to reject the visitor on its own page (inferred). That page has never been seen, so its wording is unknown.
- **A Union user never onboarded to Stargazer.** They have no role on the login app's project `stargazer`, so the gate returns Union's plain 403. The gate answering 403 to anyone without a role on the project is measured. This app's 403 is inferred.

The login app's "No workspace yet" page only reaches visitors who can view `stargazer` but don't have a project of their own. Onboarding grants both together, so in practice that's an org admin, or someone whose onboarding failed partway. Its advice ("sign in with the email address the invitation went to") is meant for people who signed in with the wrong identity. Those people are usually non-members, so they get Union's rejection instead.

The login app can't fix this because none of its code runs before the gate. Any fix has to come before the redirect. Options to weigh:

- The landing page's Log in says sign-in is invite-only, with a way to ask for access, before it forwards.
- An ungated page in front of the login app explains invites and then links into the gated app. `requires_auth` is set per app, not per path, so this would be a second app.

## First step

Sign in through `stargazer.bio/login` in a fresh browser session with an account that was never invited. Record what Union shows, then do the same with a Union user who has no `stargazer-login` policy. If Union's pages already explain the situation clearly, this ticket may not be needed.

- [x] The signed-out path up to the sign-in page (measured 2026-10-30, curl). `stargazer.bio/login/` is live and refreshes to the login app. The login app returns a 302 to the tenant's `/login`, which returns a 307 to `signin.us-west-2.unionai.cloud/oauth/v2/authorize` (Union's ZITADEL instance, scope `urn:zitadel:iam:org:roles:id:stargazerbio`). That lands on a page titled "Sign in to stargazerbio" with Continue with Google, Github (Stargazer Bio) and Microsoft, an email field, and "Need help accessing your workspace? Contact support@union.ai". There's no sign-up link. The page never mentions Stargazer.
- [ ] A never-invited account, past the provider's sign-in. This needs a person, because it means signing in to an outside account with its own credentials. Union's public docs don't describe this case.
- [ ] A Union user with no `stargazer-login` policy. The only users are the admin, who can see every project, and the test account, which has the policy. Testing this means taking the policy off the test account for a while, then giving it back with `upgrade`. The gate's decision is cached per browser session, so the check needs a fresh one.

Whatever these show, the sign-in page already gives one dead end: support@union.ai. Someone who isn't a Stargazer user will email Union rather than Stargazer.
