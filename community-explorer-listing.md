---
title: community-explorer-listing
status: review
priority: high
created: 2026-11-03
pr: 30
---

The dashboard's explorer lists `StargazerBio/community-notebooks`, the
notebooks in its `catalog.yaml` first and the rest behind a filter, from a
cached copy of the repo's tree (GitHub's anonymous API allows 60 requests an
hour). Copying one into a workspace is Open from GitHub at its commit.

The scRNA pipeline tile moves with it: infra lists it as a built-in at its
in-image path, and that file is gone from the image from the first release
after v2026.10.30 (stargazer PR 124). This has to land before infra's
`stargazer-bio` pin moves to such a release, or the tile breaks.

The infra piece of ticket [[notebooks-in-git]], left from [[publish-to-git]].

## Plan

Branch `feat/community-explorer-listing` in infra. The pixi doc edit from
[[community-catalog-pixi-headers]] rides on it.

**Listing without the API.** One download of
`github.com/<repo>/archive/refs/heads/main.tar.gz` (codeload, not the API,
so not under the 60-an-hour limit) holds every notebook's source and
`catalog.yaml`, and main's commit SHA is the tarball's pax `comment` header
(measured on the real repo: `be9ab20…`). A featured notebook pinned to
another commit is read from `raw.githubusercontent.com/<repo>/<commit>/<path>`,
also not the API. Cached in process for 10 minutes; a failed download isn't
cached.

**Two explorer sources.** Keyvalue filters apply to every source, so "the
rest behind a filter" is a source chip, not a keyvalue:

- `featured`: the catalog's notebooks, in catalog order, each at its pinned
  commit. On in the default filter (`mine`, `stargazer`, `featured`).
- `community`: every other `<domain>/<slug>.py` (not `ci/`) at main's commit,
  by path. Off by default.

An entry is a listed record: `cid` of its source bytes, `name` the file
name, `url` its GitHub page at its commit, and keyvalues a `Notebook`'s
(`title` from `main_name`, else the stem; `description` from
`main_description`; `slug` the stem) plus `domain`, `path` and `commit`.
A source that can't be read leaves the others' entries and is named in
`Stargazer-Unavailable`, like `public`.

**Download and copy.** `/assets/download/<cid>?network=featured|community`
redirects to the raw file at its commit. The card's Add to workspace posts
`/workspace/copy` with `section=community`, `slug=<commit>/<path>`; the
dashboard checks both against the layout's patterns, builds the GitHub link
for `config.COMMUNITY_REPO` itself and fetches it through
`app.github_import`, so a copy is Open from GitHub at that commit. The card
also links View on GitHub.

**The scRNA tile.** Its built-in entry goes, and with it the `workflows`
section (the `Notebook` literal, `_SECTIONS`, `_copy_source`): it is the
catalog's `scrna/clustering-pipeline.py`, listed as featured.

### Pieces

- [x] `app/community_listing.py`: fetch, parse, cache.
- [x] `app/assets.py`: the two sources, unavailability, download redirect.
- [x] `app/admin_app.py`: copy from `community`, default filter, `workflows` gone.
- [x] `app/notebooks.py`: scRNA built-in gone.
- [x] `app/static/explorer.js`: labels, card (copy, View on GitHub).
- [x] `pyyaml` named in `pyproject.toml` (it's only transitive today).
- [x] Tests: `tests/unit/test_community_listing.py` against a tarball and raw
      files served by `httpx.MockTransport`.
- [x] `docs/architecture/app.md`'s explorer section; `app_internals.md` where it names the scRNA built-in.
- [x] Verified on the tenant as the test account (`verify-dashboard`); not on the devbox, which has no path of its own here.

## Verification recipe

- **CL-1** the explorer opens with Featured on, Community off.
- **CL-2** `/assets/list?source=stargazer&source=featured&source=community`
  lists the tutorials, then the catalog's notebooks at their pinned commits,
  with no `Stargazer-Unavailable`.
- **CL-3** a featured card's Add to workspace makes a tile whose source is
  byte-identical to the raw file at the pinned commit.

Infra's `verify-dashboard` skill: `union_dashboard.py deploy` from the
branch, sign in to the console as the test account, open the dashboard with
`location.href`. CL-2 and CL-3 by `fetch` from the dashboard page (compare
`/workspace/download?slug=<slug>` with the raw URL). Delete the copy with
`POST /workspace/delete`, then `union_dashboard.py teardown`.

Locally, against the real repo:
`uv run python -c "import asyncio; from app import community_listing as c; print(asyncio.run(c.listing()))"`.

### Evidence (2026-11-06, infra PR 30)

Tenant, dashboard from `721df06`: CL-1 chips Mine/Stargazer/Featured on,
Public/Community off; CL-2 200 with 4 tutorials then scRNA at `c294e000`
and germline at `352b277f`, no unavailable header; CL-3 `scrna-seq-clustering`
identical to the pinned file (15967 bytes). Copy deleted, teardown left
live runs `[]`. Unit tests: 331 passed.

Related: [[board]], [[notebooks-in-git]], [[publish-to-git]].
