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
Microsoft, so not every user has a GitHub account. So the dashboard
proposes notebooks to one Stargazer-owned repository for them.

- **`StargazerBio/community-notebooks`, organized by topic:**
  `<domain>/<slug>/notebook.py`, e.g. `germline/tp53-qc/`. The publish
  dialog asks for the domain. Who may update a notebook is recorded in its
  folder; attribution is the commit author.
- **Publish opens a PR** with a message the user writes. The PR's author
  is the user (name from Union's `X-User-Claim-Name`); Stargazer's app
  opens it. Republish is another PR, so every version keeps its history
  and message.
- **CI is the inclusion bar, and passing PRs merge on their own.** The
  check is that the notebook parses and runs headless against its demo
  inputs (a bundle it names). A failing PR stays open, and the dashboard
  tile shows why. No lock files or image digests live in the repo: those
  belong to runs (ticket `run-records`).
- **A catalog is the curation.** Maintainers keep a `catalog.yaml` of
  featured notebooks at a commit, the way a bundle lists approved files.
  The explorer shows the catalog by default and the rest behind a filter.
  Add first-PR review per contributor only if spam appears.
- **Unpublish** opens a PR deleting the folder. Its history stays, as a
  published file's should: say so in the dialog.
- **Copy** a public notebook into a workspace is Open from GitHub at the
  commit, so a copy names exactly which version it came from.
- **Discovery:** the explorer lists the repo from a cached copy of the tree
  (GitHub's anonymous API allows 60 requests an hour), and the repo is
  browsable on GitHub as is. Anyone can also PR to it directly.

## Open questions

- **Credentials.** A GitHub App installed on that one repo, allowed to
  open and merge PRs, its key held by the dashboard. It brings back a
  long-lived GitHub secret the one-login work removed; keep user code out
  of the process that holds it (the dashboard evaluates a notebook's
  `main_env` line today, ticket `private-pinata-key`).
- **CI cost.** Running a notebook headless needs its tools; a GATK
  notebook runs only where the tools are (the image, or the devbox). Run
  the check in the Stargazer image.
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

- [ ] Decide credentials.
- [ ] Create `StargazerBio/community-notebooks`: licence, README, topic
      folders, CI that runs each changed notebook on its demo inputs,
      branch protection with auto-merge, `catalog.yaml`.
- [ ] Infra: Publish, Republish, Unpublish and Copy as PRs against it.
- [ ] Infra: the explorer lists it, the catalog first.
- [ ] Migrate existing public notebooks, then retire the public-tier path.
- [ ] Docs: `docs/architecture/notebook.md` gains how notebooks are shared.
