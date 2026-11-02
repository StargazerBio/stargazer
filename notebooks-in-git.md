---
title: notebooks-in-git
status: backlog
priority: normal
created: 2026-11-02
---

Notebooks are code, and code lives in git; the asset graph is for data.
Publishing a notebook to the public tier (ticket `public-notebooks`)
reinvents git badly: republishing deletes the previous version (measured in
that ticket: after Republish, `get(<old cid>)` is None), and there are no
diffs, change messages, review or forks, under a 9-keyvalue cap. Git has
all of that. Replace public notebooks with publishing to a git repo, then
retire them.

**Decided (2026-11-02):** code in git, data in IPFS. Tutorials and
Stargazer's workflow notebooks stay in this repo, baked into the image and
pinned by release. A notebook in any GitHub repo already opens into a
workspace (ticket `open-from-github`).

## Publishing from the dashboard

Users must be able to make a notebook public from their dashboard without
touching git. The project already tried per-user GitHub forks and dropped
them because saving cost two extra GitHub consent steps (ticket
`workspace-state-object-storage`), and Union sign-in can be Google or
Microsoft, so not every user has a GitHub account. So the dashboard commits
for them, to one Stargazer-owned repository:

- **`StargazerBio/community-notebooks`**, one directory per user
  (`users/<subject>/<slug>.py`, or a readable handle if one exists).
- **Publish** commits the workspace notebook there with a message the user
  writes in the dialog. The commit's author is the user (name from Union's
  `X-User-Claim-Name`); the committer is Stargazer's app. Republish is
  another commit, so every version keeps its history and message.
- **Unpublish** commits the file's deletion. Its history stays, as a
  published file's should: say so in the dialog.
- **Copy** a public notebook into a workspace is Open from GitHub at the
  commit, so a copy names exactly which version it came from.
- **Discovery:** the explorer lists the repo's notebooks from a cached copy
  of the tree (GitHub's anonymous API allows 60 requests an hour), and the
  repo is browsable on GitHub as is. Anyone who wants review can PR to it
  like any repo.

## Open questions

- **Credentials.** A GitHub App installed on that one repo, contents
  write only, its key held by the dashboard. It brings back a long-lived
  GitHub secret the one-login work removed; keep user code out of the
  process that holds it (the dashboard evaluates a notebook's `main_env`
  line today, ticket `private-pinata-key`).
- **Paths.** The dashboard writes only to the signed-in user's directory.
  Direct commits, or a PR per publish that the app merges, which leaves a
  place to moderate later?
- **Moderation.** Revert by hand until it's needed.
- **Licence.** The repo's licence applies to what's published; the dialog
  says which.

## Retire public notebooks

After publishing to git ships:

- Infra: the publish, republish and unpublish routes and their tiles, and
  the explorer's public `notebook` entries.
- This repo: the `Notebook` asset type (`src/stargazer/assets/notebook.py`)
  and its export, and any docs naming published notebooks as assets.
- Existing public `asset=notebook` records: commit each to the repo under
  its owner, then delete it from the public tier.

## Pieces

- [ ] Decide credentials and direct commit versus PR.
- [ ] Create `StargazerBio/community-notebooks` with its licence and README.
- [ ] Infra: Publish, Republish, Unpublish and Copy against the repo.
- [ ] Infra: the explorer lists it.
- [ ] Migrate existing public notebooks, then retire the public-tier path.
- [ ] Docs: `docs/architecture/notebook.md` gains how notebooks are shared.
