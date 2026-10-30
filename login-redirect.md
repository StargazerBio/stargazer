---
title: login-redirect
status: review
priority: normal
created: 2026-10-30
pr: 19
---

A "Log in" link on stargazer.bio that takes anyone to their own dashboard. The link is `stargazer.bio/login`; after that the user can be on Union's domains. Each dashboard lives at its project's address (`https://<project>.apps.stargazerbio.us-west-2.unionai.cloud`), and the project id can't be derived from a login: onboarding names it `u-<handle>` and adds a suffix on a collision. A static page can't see who is signed in, so one small Union app does the lookup.

Union doesn't take custom domains, so the app itself can't be served from stargazer.bio. Proxying it there wouldn't work either: Union's login gate sends the browser to the tenant's `/login` and back to the app's Union address, and the session cookies are Union's, so stargazer.bio would never see a signed-in request (inferred from the gate's measured behavior, not tested).

## Flow

1. `stargazer.bio/login` forwards straight to the login app, `https://login.apps.stargazerbio.us-west-2.unionai.cloud/`.
2. The login app runs `requires_auth=True`, so an anonymous visitor goes through Union's sign-in and comes back.
3. It verifies `X-User-Token` the way the dashboard does (infra `app/identity.py`), lists the projects the visitor can see by calling Union's `ListProjects` with that token, and 302s to the one labeled `union-subject=<subject>` (onboarding's label).
4. The dashboard's own gate passes on the session the user just made, with no second sign-in (measured).

## Pieces

- [x] Login app in infra `app/login.py`, deployed by `upgrade` (`deploy_login`) into its own project `stargazer`. Onboarding gives every user the policy `stargazer-login` (viewer there), and `upgrade` gives it to existing users (infra PR #19)
- [x] The lookup: neither an org-wide key nor a map. The visitor's own ID token, sent as `Bearer` to `ListProjects`, lists exactly the projects they can view (measured with a probe app in `u-pryce`), and the subject label picks theirs
- [x] A signed-in user with no project gets a "No workspace yet" page (404)
- [ ] Startup latency: a scaled-to-zero redirect app adds its cold start to the dashboard's. Measure it and decide on a minimum of one replica
- [x] `stargazer.bio/login` forwarding to the app: `login/index.html` in `StargazerBio/stargazer.bio` (GitHub Pages, PR #1 there), which merges after infra PR #19 is deployed

## Verification (2026-10-30, from the branch at `bc917a3`)

- Test account, signed in, in the built-in browser: the login app landed on `https://u-pryce.apps.stargazerbio.us-west-2.unionai.cloud/` and the dashboard rendered, with no second sign-in.
- Not signed in (curl): 302 to the tenant's `/login?redirect_url=` the login app.
- The admin, who has no Stargazer project (bearer token): 404 "This account doesn't have a Stargazer workspace." in 0.17–0.35 s with the app already running.
- Not checked: the whole path from `stargazer.bio/login`, which needs the DNS, and signing in from a signed-out browser (the browser pane's session is the test account's and isn't signed out).

## Verification recipe

As the test account in a fresh browser session: open `stargazer.bio/login`, sign in through Union, land on `u-pryce`'s dashboard with no second sign-in prompt. Then, already signed in, open it again and land there directly. A Union user with no Stargazer project gets the no-workspace page.
