---
title: sdk-package
status: done
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

## Shelved (2026-10-27)

Back to `maybe`. The SDK runs from source everywhere: a checkout locally
(`uv pip install -e .`), the checkout's recipe for task images, the source
tree copied into the notebook image, Flyte's code bundle for dashboards, and
the sibling checkout for infra. Shipping it as a package adds an installed
copy with no source beside it, and every one of those places would need a
second path for it. Splitting the app into its own repo would make that
path mandatory, and 17 of the last 40 merged PRs touched both `src/` and
`app/`. Public notebooks stay runnable without releases as long as the SDK
in the image is the one they were written against; before 1.0 there's no
compatibility promise. Revisit if an outside user needs to pin SDK
versions, or a published notebook needs one (a git commit in its PEP 723
header would do, without a release).

Came out of a 2026-10-14 brainstorm on splitting the repo. The conclusion was
to stay one repo and package only the SDK: `app/` is deployment code that runs
from this repo and is never a distribution of its own. The import-layer rule
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
- [x] **No published task images.** Decided 2026-10-27: Stargazer never
      publishes task images. Images build from their recipe when a run asks
      for them, and published ones would multiply per release. PR #92
      (`feat/sdk-task-images`), which published `stargazer-gatk` and
      `stargazer-scrna` to GHCR per version, is closed unmerged. Its devbox
      measurement still holds: a workflow's child tasks run on the
      submitter's images, whatever their pod has installed.
- [ ] **Package only the SDK.** The root project becomes `stargazer-bio` and
      its wheel holds `src/stargazer` alone. There is no app distribution:
      `app/` stays in this repo, runs from a checkout, and is never published.
      Its dependencies (the `landing` and `app` extras) come off the SDK's
      published metadata, for example into a dependency group. Check what
      assumes `app` is installed with the package: the dashboard image
      (`with_uv_project` on the root `pyproject.toml` with `--extra landing`
      and `install_project`), the notebook image (installs `/stargazer`
      editable), the infra repo (`stargazer[app]` as an editable path
      dependency, importing `app.deploy` and `app.config`), the test tiers,
      and pre-commit.
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
      Shipped in PR #87 (merge `fdec272`): `Asset.declared_fields()` replaces the
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
  confirm its tasks run remotely.
- Confirm a dashboard-only release leaves the notebook image's URI unchanged.

## Outcome

Delivered by ticket `split-app-repo` (StargazerBio/stargazer#102): the
package is the SDK alone, `stargazer-bio`, with the app tier moved to infra
and the runtime kept out of the package in `runtime/`. Publishing it is
ticket `pypi-release`.
