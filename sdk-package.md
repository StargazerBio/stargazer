---
title: Ship the SDK as its own package
status: backlog
priority: low
created: 2026-10-14
---

Make the SDK (`src/stargazer`: assets, tasks, workflows, utils, config, the
MCP server) installable and usable on its own, from this repo, without the app
tier and without a source checkout. Today the one `stargazer` distribution
ships `app/` too, and the task images only build from a checkout. This is the
groundwork for publishing (ticket `pypi-release`) and for notebook images
that change base only when the SDK version does (see ticket
`notebook-declared-image`, Deferred).

Came out of a 2026-10-14 brainstorm on splitting the repo. The conclusion was
to stay one repo but ship separate distributions. The import-layer rule
(TID251) already keeps the SDK from importing `app/`, which is most of what a
split buys. A real repo split is worth it only if one of these comes true: a
public SDK with a private platform, outside users pinning SDK versions,
separate owners for the bioinformatics and platform sides, or release cadences
that fight.

## Findings (measured 2026-10-14)

A wheel built from the branch archive (`uv build --wheel`) and installed into
a clean venv outside any checkout:

- The wheel contains `stargazer/` and all of `app/` (`packages.find` includes
  `app*`), so SDK users also get the dashboard and onboarding code.
- `import stargazer`, `stargazer.config`, `stargazer.tasks` and
  `stargazer.assets` all import.
- `PROJECT_ROOT` (`Path(__file__).resolve().parents[2]` in `config.py`)
  resolved to `<venv>/lib/python3.13`. `gatk_env` and `scrna_env` build with
  `with_uv_project(PROJECT_ROOT / "pyproject.toml",
  project_install_mode="install_project")`, so their images point at a
  project that isn't there. `gatk_env.image.uri` still computed
  (`localhost:30000/stargazer-gatk:…`), so nothing fails until a remote run
  builds the image. Not run: that build, which is expected to fail or package
  the wrong directory.
- The default registry outside a checkout is the devbox's `localhost:30000`,
  since `STARGAZER_TARGET` defaults to `devbox`.

## Plan

- [x] **Decide where the notebooks live.** Settled 2026-10-17. The tutorials
      and `notebook_base` stay in the package, so the tutorials keep importing
      each other as `stargazer.notebooks.tutorials.*`. Other notebooks, the
      scRNA notebook first, live in a top-level `notebooks/` folder that no
      distribution ships, and the workspace seeds move to `app/` (ticket
      `top-level-notebooks`). Snapshots go (ticket `save-whole-workspace`).
- [ ] **Versioned, published task images.** A task's code runs from its image,
      so the image must carry the same `stargazer` version as the caller.
      Publish the gatk and scrna images per release (for example
      `ghcr.io/stargazerbio/stargazer-gatk:<version>`) and have the
      environments use them via `from_base` outside a checkout, keeping
      checkout builds for development. Don't make users rebuild the bioconda
      image: it's slow, and two builds of one version could differ.
- [ ] **Split the distributions in a uv workspace.** `stargazer` (the SDK) and
      `stargazer-app` (`app/` with its own `pyproject.toml`, the
      `stargazer-users` entry point, and the `landing`/`app` extras), the app
      depending on the SDK through a workspace source in development and a
      version pin in releases. Check what assumes `app` is installed: the
      dashboard image (`with_uv_project` on the root `pyproject.toml`), the
      notebook image (installs `/stargazer` editable), the test tiers, and
      pre-commit.
- [ ] **Notebook image on a released SDK.** Install the built wheel (or a
      pinned version) instead of copying `src/` and `app/` into `/stargazer`.
      The base then changes only when the SDK version or the pod
      infrastructure does, not on every commit. This also gives
      `bit-for-bit-snapshots` an SDK version to record.
- [ ] **Clean the seam.** Remove `app/`'s import of the private
      `stargazer.assets.asset._BASE_FIELDS`. Write the runtime contracts down
      in one architecture doc, since they become the SDK/app API: the asset
      keyvalue schema, the index HTTP API (server in `app/`, client in the
      SDK), and the dashboard-to-pod env vars (`STARGAZER_INDEX_URL`,
      `STARGAZER_STORE_ROOT`, `STARGAZER_OWNER`, `STARGAZER_NOTEBOOK_IMAGE`).

## Open questions

- Where to publish: PyPI (as `pypi-release` assumes), a private index, or
  GitHub releases.
- Whether a released SDK carries a compatibility promise. Outside users
  pinning versions is where AGENTS.md's "don't consider backwards
  compatibility" starts to bend.

## Verification

- Install the SDK wheel into a clean venv outside a checkout, then run a
  gatk task and an scrna task remotely on Union, and on the devbox.
- Launch a notebook on a notebook image built from a released SDK version and
  confirm its tasks run on the matching task images.
- Confirm a dashboard-only release leaves the notebook image's URI unchanged.
