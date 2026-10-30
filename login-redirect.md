---
title: login-redirect
status: backlog
priority: normal
created: 2026-10-30
---

A "Log in" link on stargazer.bio that takes anyone to their own dashboard. The link is `stargazer.bio/login`; after that the user can be on Union's domains. Each dashboard lives at its project's address (`https://<project>.apps.stargazerbio.us-west-2.unionai.cloud`), and the project id can't be derived from a login: onboarding names it `u-<handle>` and adds a suffix on a collision. A static page can't see who is signed in, so one small Union app does the lookup.

Union doesn't take custom domains, so the app itself can't be served from stargazer.bio. Proxying it there wouldn't work either: Union's login gate sends the browser to the tenant's `/login` and back to the app's Union address, and the session cookies are Union's, so stargazer.bio would never see a signed-in request (inferred from the gate's measured behavior, not tested).

## Flow

1. `stargazer.bio/login` forwards straight to the redirect app's Union address.
2. The redirect app runs `requires_auth=True`, so an anonymous visitor goes through Union's sign-in and comes back.
3. It verifies `X-User-Token` the way the dashboard does (infra `app/identity.py`), finds the Stargazer project labeled `union-subject=<subject>` (onboarding's label) and 302s to that project's dashboard.
4. The dashboard's own gate should pass on the session the user just made, with no second sign-in (inferred, check it).

## Pieces

- [ ] Redirect app in infra `app/`, deployed by infra like the dashboard. It lives in a project every Stargazer user can view, since the gate needs view on the app's project (measured): onboarding grants that view, and `upgrade` grants it to existing users
- [ ] The lookup: listing projects needs a key that can read them org-wide. The alternative is a subject → project map that onboarding writes. Pick one
- [ ] A signed-in user with no project gets a plain page saying they don't have a workspace yet, not an error
- [ ] Startup latency: a scaled-to-zero redirect app adds its cold start to the dashboard's. Measure it and decide on a minimum of one replica
- [ ] `stargazer.bio/login` forwarding to the app. The landing page lives in `StargazerBio/stargazer.bio` (GitHub Pages, PR #1 there), whose `login/index.html` forwards to the tenant's sign-in for now. Point it at the app's address

## Verification recipe

As the test account in a fresh browser session: open `stargazer.bio/login`, sign in through Union, land on `u-pryce`'s dashboard with no second sign-in prompt. Then, already signed in, open it again and land there directly. A Union user with no Stargazer project gets the no-workspace page.
