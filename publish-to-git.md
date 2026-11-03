---
title: publish-to-git
status: doing
priority: normal
created: 2026-11-03
---

The dashboard's Publish, Republish and Unpublish put a workspace notebook in
`StargazerBio/community-notebooks` instead of on the public tier: the infra
piece of [[notebooks-in-git]].

- **Publish** asks for the notebook's name (its slug, prefilled with the
  workspace notebook's), a domain, its demo bundle and a message. It writes
  `<domain>/<slug>.py` with `owners` and `demo_bundle` set in its
  `[tool.stargazer]` header, on a branch `publish/<domain>/<slug>`, opens a
  PR authored by the dashboard's GitHub App, and turns on auto-merge, so CI
  passing merges it.
- **Republish** resets that branch to `main` and commits the new version, so
  an open PR picks it up and a merged one gets a new PR.
- **Unpublish** deletes the file in a commit straight to `main` (the App is
  on the ruleset's bypass list); a notebook whose PR hasn't merged has its PR
  closed instead.
- **Owners** are Union subjects; `maintainers` is the org admins
  (`STARGAZER_ADMIN_SUBJECTS`). Writing to a path someone else owns is
  refused.
- The dashboard records each workspace notebook's published path and PR in
  its state table, so the tile shows Republish, Unpublish and a link.

Credential: a GitHub App, `Stargazer Notebooks`, installed on
community-notebooks only, its private key the Flyte secret
`stargazer-github-app-key`, its ID `STARGAZER_GITHUB_APP_ID` in `tenant.env`.
The user creates the App, the ruleset and the secret.

Not here: the tile showing why CI failed (it links the PR), the explorer
listing the repo, retiring the public-tier path, migrating public notebooks.

- [ ] Unit tests against a fake GitHub
- [ ] `app/community_notebooks.py` and the publish routes
- [ ] Publish dialog
- [ ] Verified on the tenant as the test account

Related: [[board]], [[notebooks-in-git]].
