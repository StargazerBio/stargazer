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

- [x] **Decide where the notebooks live.** Settled 2026-10-21. The tutorials,
      the scRNA notebook, the workspace seeds and `notebook_base` all stay in
      the package for now, so the tutorials keep importing each other as
      `stargazer.notebooks.tutorials.*`. Moving the scRNA notebook to a
      top-level `notebooks/` folder and the seeds to `app/` is shelved (ticket
      `top-level-notebooks`). Snapshots go (ticket `save-whole-workspace`).
- [x] **Versioned, published task images.** A task's code runs from its image,
      so the image must carry the same `stargazer` version as the caller.
      Publish the gatk and scrna images per release (for example
      `ghcr.io/stargazerbio/stargazer-gatk:<version>`) and have the
      environments use them via `from_base` outside a checkout, keeping
      checkout builds for development. Don't make users rebuild the bioconda
      image: it's slow, and two builds of one version could differ.
      Done on `feat/sdk-task-images`: `task_image` in `stargazer.config`
      builds the recipe when the package's root has a `pyproject.toml` (a
      checkout, editable installs included) and otherwise runs
      `ghcr.io/stargazerbio/<image>:<installed version>`. The **Task images**
      workflow (`.github/workflows/task-images.yml`) publishes both on a `v*`
      tag, refusing one that doesn't match the project version, and on
      `workflow_dispatch`, via `cli/publish_task_images.py`, which builds the
      same `flyte.Image` recipes. The version is read from the `stargazer`
      distribution's metadata, so the distribution split's rename to
      `stargazer-bio` changes `published_image` (and the publish script) with
      it. After the first publish, make the new `stargazer-gatk` and
      `stargazer-scrna` GHCR packages public: new org packages start internal.
- [ ] **Split the distributions in a uv workspace.** `stargazer-bio` (the SDK) and
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
- [x] **Clean the seam.** Remove `app/`'s import of the private
      `stargazer.assets.asset._BASE_FIELDS`. Write the runtime contracts down
      in one architecture doc, since they become the SDK/app API: the asset
      keyvalue schema, the index HTTP API (server in `app/`, client in the
      SDK), and the dashboard-to-pod env vars (`STARGAZER_INDEX_URL`,
      `STARGAZER_STORE_ROOT`, `STARGAZER_OWNER`, `STARGAZER_NOTEBOOK_IMAGE`).
      Done on `refactor/sdk-seam`: `Asset.declared_fields()` replaces the
      import, and the contract is the "Contract with the SDK" section of
      `docs/architecture/app.md`. There is no index HTTP API (every pod opens
      the index from its URL), so the doc records the URL and table instead.
      Still crossing the seam privately: `app/assets.py` imports
      `stargazer.utils.pinata._stamp_owner`, and `app/notebook_agent.md`
      shows `from stargazer.utils import _run`.

## Decisions (2026-10-26)

- **Published to PyPI as `stargazer-bio`.** `stargazer` on PyPI is taken by
  an unrelated package (StatsReporting's regression tables, checked
  2026-10-26). The import name stays `stargazer`; only the distribution is
  `stargazer-bio`, and notebooks pin `stargazer-bio == X.Y.Z`.
- **No compatibility promise before 1.0.** Releases are `0.x` and any can
  break, so AGENTS.md's "don't consider backwards compatibility" stands for
  the SDK until a 1.0 release.

## Verification

- Install the SDK wheel into a clean venv outside a checkout, then run a
  gatk task and an scrna task remotely on Union, and on the devbox.
- Launch a notebook on a notebook image built from a released SDK version and
  confirm its tasks run on the matching task images.
- Confirm a dashboard-only release leaves the notebook image's URI unchanged.
