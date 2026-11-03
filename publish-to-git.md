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
  workspace notebook's), a domain and a message, and commits
  `<domain>/<slug>.py` to `main` with `owners` set in its `[tool.stargazer]`
  header. No branch, no PR: the repo has no branch protection and its CI only
  checks the layout.
- **Republish** commits the new version to the same path.
- **Unpublish** deletes the file in a commit to `main`.
- **Owners** are Union subjects; `maintainers` is the org admins
  (`STARGAZER_ADMIN_SUBJECTS`). Writing to a path someone else owns is
  refused.
- The dashboard records each workspace notebook's published path in its
  state table, so the tile shows Republish, Unpublish and a link to the file.

Credential: the org's existing GitHub App, `stargazer-workspaces`, given
Pull requests write (unused now) and installed on community-notebooks only. Its private
key is the Flyte secret `stargazer-github-app-key`, its ID
`STARGAZER_GITHUB_APP_ID` in `tenant.env`. The user updated and installed the
App and created the secret (done 2026-11-03).

Not here: the explorer
listing the repo, retiring the public-tier path, migrating public notebooks.

- [x] Unit tests against a fake GitHub
- [x] `app/community_notebooks.py` and the publish routes
- [x] Publish dialog
- [ ] Verified on the tenant as the test account (needs community-notebooks
      #2 merged, so the repo is on the single-file layout)

Related: [[board]], [[notebooks-in-git]].
