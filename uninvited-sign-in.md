---
title: uninvited-sign-in
status: done
priority: normal
created: 2026-10-30
pr: 6
---

A visitor without an invite who clicks Log in on stargazer.bio gets stuck at Union's sign-in. They never reach anything Stargazer controls. `stargazer.bio/login` forwards to the login app (infra `app/login.py`). That app is `requires_auth=True`, so Union's gate runs first:

- **No Union account.** Union's sign-in offers Google, GitHub and Microsoft (measured). Union doesn't create a user on first sign-in (ticket [[self-serve-onboarding]]), so I expect Union to reject the visitor on its own page (inferred). That page has never been seen, so its wording is unknown.
- **A Union user never onboarded to Stargazer.** They have no role on the login app's project `stargazer`, so the gate returns Union's plain 403. The gate answering 403 to anyone without a role on the project is measured. This app's 403 is inferred.

The login app's "No workspace yet" page only reaches visitors who can view `stargazer` but don't have a project of their own. Onboarding grants both together, so in practice that's an org admin, or someone whose onboarding failed partway. Its advice ("sign in with the email address the invitation went to") is meant for people who signed in with the wrong identity. Those people are usually non-members, so they get Union's rejection instead.

The login app can't fix this because none of its code runs before the gate. Any fix has to come before the redirect. Options to weigh:

- The landing page's Log in says sign-in is invite-only, with a way to ask for access, before it forwards.
- An ungated page in front of the login app explains invites and then links into the gated app. `requires_auth` is set per app, not per path, so this would be a second app.

## First step

Sign in through `stargazer.bio/login` in a fresh browser session with an account that was never invited. Record what Union shows, then do the same with a Union user who has no `stargazer-login` policy. If Union's pages already explain the situation clearly, this ticket may not be needed.

- [x] The signed-out path up to the sign-in page (measured 2026-10-30, curl). `stargazer.bio/login/` is live and refreshes to the login app. The login app returns a 302 to the tenant's `/login`, which returns a 307 to `signin.us-west-2.unionai.cloud/oauth/v2/authorize` (Union's ZITADEL instance, scope `urn:zitadel:iam:org:roles:id:stargazerbio`). That lands on a page titled "Sign in to stargazerbio" with Continue with Google, Github (Stargazer Bio) and Microsoft, an email field, and "Need help accessing your workspace? Contact support@union.ai". There's no sign-up link. The page never mentions Stargazer.
- [x] A never-invited account, past the provider's sign-in (measured 2026-10-31 by the user, with a brand-new GitHub account in a private window). Union's sign-in page reloads with a yellow notice: "Identity provider sign-in failed. We could not get an email address for this sign-in. Check that your provider account has a verified email. If it does, contact support. Reference: V2_…". This doesn't say "not invited". It means Union failed earlier, at reading the account's email, so it may not be the error a stranger with a verified, public email gets. Either way the visitor is told to contact Union's support.
- [ ] The same, with a GitHub account whose email is verified and set public, to see Union's actual not-a-member error.
- [x] A Union user with no `stargazer-login` policy (measured 2026-10-31). I removed the test account's assignment at 04:06:52 UTC, leaving it only `stargazer-u-pryce`. In the built-in browser, signed in as the test account, the login app then returned HTTP 403: `text/plain`, body `Forbidden`, server `cloudflare`, on a blank dark page. It has no text, no link back, and no mention of Stargazer or Union, and it came straight away with no sign-in step. I gave the assignment back at 04:07:18. The gate still answered 403 four seconds later, which is its per-session cache. At 04:11 it sent the browser to sign in again. After GitHub SSO, the login app passed the test account through to `u-pryce`'s dashboard, so access is back.

Whatever these show, the sign-in page already gives one dead end: support@union.ai. Someone who isn't a Stargazer user will email Union rather than Stargazer.

## Change

The first option, in `StargazerBio/stargazer.bio` PR #6: `stargazer.bio/login` stops on an invite-only page with Continue to sign in and Request access (mailto pryce@stargazer.bio). A browser that has continued once skips the page after that. It was verified locally in headless Chrome against a stubbed login app; the PR has the evidence.

## Outcome

Shipped in StargazerBio/stargazer.bio#6 (`e036470`), merged 2026-10-31.
Verified locally in headless Chrome against a stubbed login app (the PR has
the evidence); on the live domain, `https://stargazer.bio/login/` now serves
the invite-only page with Continue to sign in and Request access (measured
2026-10-31, curl). Left: the open checkbox above, what Union shows an
uninvited account with a verified, public email. The PR had no review
comments.

Related: [[board]].
