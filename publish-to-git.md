---
title: publish-to-git
status: done
pr: 29
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
- [x] Verified on the tenant as the test account (2026-11-03): publish
      `91ff2ad`, republish `a2a702a`, unpublish `6004f43` of
      `test/publish-check.py`

## Verification recipe

1. `set -a; . ./tenant.env; set +a`, then
   `uv run python .claude/skills/verify-dashboard/scripts/union_dashboard.py deploy`
   from the infra worktree.
2. Signed in to the console, open the test account's dashboard; its tiles
   offer Publish.
3. Create a throwaway workspace notebook, Publish it to domain `test`, and
   check `gh api 'repos/StargazerBio/community-notebooks/commits?path=test/<name>.py'`:
   the user's name as author, `stargazer-workspaces[bot]` as committer, and
   `owners` the test account's subject in the file's header.
4. Change its description through its setup, Republish (the dialog locks
   name and domain), and see a second commit with the change. Unchanged
   content makes no commit.
5. Unpublish: a delete commit, the path 404s, the tile offers Publish again.
6. Delete the notebook, `union_dashboard.py teardown`, and confirm no app
   or run is left up.

## Outcome

Shipped in infra PR 29 (`19fc9fc`): Publish, Republish and Unpublish commit
to `StargazerBio/community-notebooks` as the `stargazer-workspaces` App, with
owners in each notebook's header. Verified by unit tests against a fake GitHub
and on the tenant as the test account (commits above). The 403 on someone
else's path is unit-tested only.

Left: the explorer listing the repo (ticket [[community-explorer-listing]]);
retiring the public-tier listing and the App's unused Pull requests write
(ticket [[retire-public-notebooks]]).

Related: [[board]], [[notebooks-in-git]], [[community-explorer-listing]], [[retire-public-notebooks]].
