---
title: notebooks-in-git
status: review
priority: normal
created: 2026-11-02
pr: 121
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
- **SDK drift.** In this repo a notebook is tested against the SDK at the
  same commit, so a change that breaks it fails here. In the community repo
  it's tested against a release. Run the community repo's CI against each
  new release (and optionally `main`), so a break shows up as a failing
  notebook there before or as the release ships.

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

- **Layout:** `<domain>/<slug>/notebook.py` plus `meta.yaml` with `owners`
  (Union user names, `maintainers` for the repo's own) and `demo_bundle`.
  Every notebook file is `notebook.py`, so each must declare `main_name`
  (Open from GitHub names a file without one after its stem); the layout
  check enforces it.
- **CI:** a layout check; each changed notebook runs
  `marimo export html --sandbox ... -- --run` in the Stargazer image on an
  empty store holding only its demo bundle; every notebook daily on
  `latest` (instead of a cross-repo dispatch from the release workflow,
  which would need a token here); manual runs take an image tag.
- **`--run`:** `mo.app_meta().mode` is `edit` under `marimo export`
  (measured), so a notebook can't detect a headless run that way. CI passes
  `-- --run` and a notebook gates button-held work on
  `"run" in mo.cli_args()`.
- **Licence:** MIT, as this repo.
- **Credentials:** still open; the GitHub App on that one repo remains the
  plan.

## Pieces

- [ ] Decide credentials.
- [x] Build `StargazerBio/community-notebooks`' content: licence, README,
      topic folders, CI that runs each changed notebook on its demo inputs,
      `catalog.yaml`.
- [ ] Create the repo, push the bundle, set branch protection requiring
      the `Notebooks` checks, allow auto-merge. Do this before merging PR 121.
- [ ] Infra: Publish, Republish, Unpublish and Copy as PRs against it.
- [ ] Infra: the explorer lists it, the catalog first.
- [x] Move the scRNA pipeline notebook there (`scrna/clustering-pipeline`),
      with its demo bundle named, in the catalog. Remove
      `notebooks/workflows/` from this repo and the image, and its smoke
      test entries (PR 121).
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

Dashboard: Open from GitHub with a link to `<domain>/<slug>/notebook.py`.
Locally: the folder's notebook in the Stargazer image.

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
