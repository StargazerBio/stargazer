---
title: release-task-images
status: backlog
priority: normal
created: 2026-11-04
blocked_by:
  - pixi-layer-cache
---

A release publishes the task images, and an installed `stargazer-bio` runs its tasks on them instead of building from source. Today `gatk_env` and `scrna_env` build from `PROJECT_ROOT / "pyproject.toml"`, which exists only in a checkout or the notebook image's `/stargazer`. Installed from PyPI, `PROJECT_ROOT` is `<venv>/lib/python3.14` and the build fails (measured 2026-11-04 with the wheel in a clean venv: `FileNotFoundError: Pixi manifest file .../lib/python3.14/pyproject.toml does not exist`), so SDK authoring from an IDE can't run a task remotely.

One recipe, two sources for the image:

- **Release:** `.github/workflows/release.yml`, which already pushes the notebook image to GHCR, builds both task images from the tagged checkout with the same `_task_image` recipe and pushes them under the release's version.
- **Installed package:** with no `pyproject.toml` beside it, `gatk_env` and `scrna_env` use the published image of the installed version, so nothing builds on first run.
- **Checkout:** builds from source as now, non-editable, the environment layer cached apart from the source.

With releases on prebuilt images, the notebook headers can install the released package instead of `/stargazer` editable, so production has no editable installs (with ticket [[pixi-notebook-sandbox]]).

Open: whether Union pulls a public GHCR image for a task as it does for notebook apps, and how a hosted notebook kernel's `with_*` layers on top of a task image (`main_env`) reference the published base.

Related: [[board]], [[pixi-layer-cache]], [[pixi-notebook-sandbox]], [[pixi-dependencies]], [[flyte-images]].
