---
title: notebooks-in-git
status: review
priority: normal
created: 2026-11-02
pr: 124
---

Notebooks are code, and code lives in git; the asset graph is for data.
Publishing a notebook to the public tier (ticket `public-notebooks`)
reinvents git badly: republishing deletes the previous version (measured in
that ticket: after Republish, `get(<old cid>)` is None), and there are no
diffs, change messages, review or forks, under a 9-keyvalue cap. Git has
all of that. Replace public notebooks with publishing to a git repo, then
retire them.

**Decided (2026-11-02):** code in git, data in IPFS. The tutorials stay
in this repo, baked into the image and pinned by release. Workflow
notebooks move to the community repo, Stargazer's own included: the scRNA
pipeline (`src/stargazer/notebooks/workflows/scrna_pipeline.py`) and the
germline notebook (ticket `germline-notebook`), as its first entries and
the examples of what a published notebook looks like. A notebook in any
GitHub repo already opens into a workspace (ticket `open-from-github`).

## Publishing from the dashboard

Users must be able to make a notebook public from their dashboard without
touching git. The project already tried per-user GitHub forks and dropped
them because saving cost two extra GitHub consent steps (ticket
`workspace-state-object-storage`), and Union sign-in can be Google or
Microsoft, so not every user has a GitHub account. So the dashboard
proposes notebooks to one Stargazer-owned repository for them.

- **`StargazerBio/community-notebooks`, organized by topic:**
  `<domain>/<slug>.py`, e.g. `germline/tp53-qc.py`. The user sets both
  in the publish dialog: the slug is the notebook's name as they give it,
  and the domain is theirs to choose. Who may update a notebook is recorded in the
  notebook itself; attribution is the commit author.
- **Publish is a commit to `main`**, with a message the user writes and
  their name as its author (from Union's `X-User-Claim-Name`); Stargazer's
  App makes it. Republish is another commit, so every version keeps its
  history and message. No PRs, no review, no branch protection: the repo is
  where notebooks are published (decided 2026-11-03). CI only checks the
  layout, and reports. No lock files or image digests live in the repo:
  those belong to runs (ticket `run-records`).
- **A catalog is the curation.** Maintainers keep a `catalog.yaml` of
  featured notebooks at a commit, the way a bundle lists approved files.
  The explorer shows the catalog by default and the rest behind a filter.
  Add first-PR review per contributor only if spam appears.
- **Unpublish** deletes the notebook in a commit to `main`. The app checks
  the caller is in its `owners` first. Its history stays, as a published
  file's should: say so in the dialog.
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
- **Licence.** The repo's licence applies to what's published; the dialog
  says which.
- **SDK drift.** In this repo a notebook is tested against the SDK at the
  same commit, so a change that breaks it fails here. The community repo
  doesn't run its notebooks, so a release that breaks one shows up only
  when someone runs it.

## Retire public notebooks

After publishing to git ships:

- Infra: the publish, republish and unpublish routes and their tiles, and
  the explorer's public `notebook` entries.
- This repo: the `Notebook` asset type (`src/stargazer/assets/notebook.py`)
  and its export, and any docs naming published notebooks as assets.
- Existing public `asset=notebook` records: commit each to the repo under
  its owner, then delete it from the public tier.

## Progress (2026-11-02)

The repo's content is built: two commits (`ed25a84`, `182d5d1`) handed over
as a git bundle in the session that opened PR 121, since that session could
neither create the repo nor reach infra. Best guesses made there, to
revisit:

- **Layout:** one file per notebook, `<domain>/<slug>.py`, with a
  `[tool.stargazer]` table in its PEP 723 script header naming `owners`
  (Union subjects, `maintainers` for the org's admins). (`demo_bundle` went
  with the notebook runs.)
  uv keeps the table when it edits the header's dependencies. Each notebook
  declares `main_name` and `main_description` for its tile; the layout check
  enforces both. (The first cut was a `<slug>/` folder holding `notebook.py`
  and `meta.yaml`; changed 2026-11-03, since it named every notebook the same
  and kept its metadata apart from it.)
- **CI:** the layout check, on pushes and PRs. The first cut also ran each
  changed notebook headless in the Stargazer image on its demo bundle, and
  every notebook daily; removed 2026-11-03 (community-notebooks #2) as more
  than the repo needs.
- **`--run`:** `mo.app_meta().mode` is `edit` under `marimo export`
  (measured), so a notebook can't detect a headless run that way. CI passes
  `-- --run` and a notebook gates button-held work on
  `"run" in mo.cli_args()`.
- **Licence:** MIT, as this repo.
- **Credentials:** the org's `stargazer-workspaces` App, installed on that
  one repo with Contents and Pull requests write (ticket [[publish-to-git]]).

## Pieces

- [ ] Decide credentials.
- [x] Build `StargazerBio/community-notebooks`' content: licence, README,
      topic folders, CI that runs each changed notebook on its demo inputs,
      `catalog.yaml`.
- [x] Create the repo, push the bundle, set branch protection requiring
      the `Notebooks` checks, allow auto-merge. Done 2026-11-03: public, `main` requires `layout` and `plan`. The `run (<folder>)` jobs are named per matrix entry, so they can't be required yet: a gate job that needs `run` would make them required.
- [ ] Infra: Publish and Republish as PRs against it, Unpublish as a
      commit to `main`, Copy as Open from GitHub.
- [ ] Infra: the explorer lists it, the catalog first.
- [x] Move the scRNA pipeline notebook there (`scrna/clustering-pipeline`),
      with its demo bundle named, in the catalog. Remove
      `notebooks/workflows/` from this repo and the image, and its smoke
      test entries (PR 124; PR 121 closed when its branch was renamed).
- [ ] Infra: the dashboard lists the scRNA notebook from the catalog, not
      as a built-in. Must land before infra's pin moves to a release
      without `notebooks/workflows/`.
- [x] Docs here: `docs/architecture/notebook.md` (the Workflows notebook
      type, Workflow graduation, Copy to workspace) and
      `docs/getting-started.md` (the image's `workflows/` folder).
- [ ] Migrate existing public notebooks, then retire the public-tier path.
- [x] Docs: `docs/architecture/notebook.md` gains how notebooks are shared
      (its Sharing Notebooks section; extend it with dashboard publishing
      when that ships).

## Verification recipe: community notebooks

A pipeline notebook runs from the community repo exactly as CI and a
dashboard user run it: headless, from its folder, on an empty store holding
only its demo bundle.

### Sub-features

- **CN-1** a notebook folder runs every cell headless and exits 0.
- **CN-2** the stored outputs are linked back to the demo inputs.
- **CN-3** the layout check passes the repo and flags a bad folder.

### How to get to it (user POV)

Dashboard: Open from GitHub with a link to `<domain>/<slug>.py`.
Locally: the notebook file in the Stargazer image.

### Driving it

- In the image (CN-1), from a community repo checkout:
  `mkdir -m 777 -p out && docker run --rm --platform linux/amd64 -v "$PWD":/repo:ro -v "$PWD/out":/out --entrypoint /repo/ci/run_notebook.sh ghcr.io/stargazerbio/stargazer /repo/<domain>/<slug> /out`
  exits 0; `out/<domain>--<slug>.log` has no traceback.
- Without the image (CN-1, CN-2): the verify-stargazer skill's local
  notebook setup, then
  `uv run --all-extras marimo export html <folder>/notebook.py -o "$RUN_DIR/evidence/x.html" -- --run`
  from a stargazer checkout (the header's `/stargazer` source exists only
  in the image, so no `--sandbox`). Then `assemble()` the outputs and
  check their `source_cid`/`reference_cid` chains.
- CN-3: `uv run --no-project --with "pyyaml>=6,<7" python ci/check_layout.py`
  exits 0.

### Gotchas

- `export A=x B=$A/y` expands `$A` before it's set: export the run dir
  first.
- The TP53 fixtures in `tests/fixtures/general` have the
  `variant_calling_demo` bundle's exact CIDs, so seeding from them stands
  in for the bundle where the gateway is unreachable. `scrna_demo` has no
  fixture copy; the synthetic fixture gives one Leiden cluster.
- `App.run(defs={"cohort": ...})` runs the cells downstream of a value
  without the cells that make it: a way to check a notebook's later
  sections on fixture outputs.

### Evidence (2026-11-02, PR 121)

Local only; the image (GHCR blobs) and IPFS gateways were blocked. scRNA
CN-1/CN-2: exit 0, both samples through all six stages, `n_obs` matching
the files, `source_cid` chained to the seeded raw files. Germline: exit 0
without `--run`; with it, the workflow started and failed on `samtools`
missing; sections 4–5 on fixture outputs gave a 5-row lineage table and
46 sites (SNP 25, deletion 14, insertion 8, symbolic 3). CN-3: passes,
flags a bad folder. Not yet run: the image path and GitHub Actions.

### Evidence (2026-11-03, community-notebooks PR 1)

In the released image (v2026.10.30) on GitHub Actions. The first run on
`main` failed both notebooks at the bundle fetch (`/opt/mcp` isn't in that
release); community-notebooks PR 1 fetches with a venv uv builds from the
image's `/stargazer`. With it, every check passes: germline ran the full
workflow with `--run` (section 5: 47 sites across 1 sample), and scRNA ran
every cell on `scrna_demo`.

Related: [[germline-notebook]], [[public-notebooks]], [[board]].
