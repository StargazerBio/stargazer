---
title: slim-image-dev-deps
status: done
priority: low
created: 2026-10-13
---

Image builds sync the project's default dependency groups, so the `dev` group
ships in every image. Flyte's uv-project layer runs `uv sync --active
--inexact` with only the `extra_args` we pass (`--extra bio`, `--extra
landing`), and the Dockerfile runs `uv sync --extra ...`, neither with
`--no-dev`. `uv export --frozen --extra bio` lists pytest, ruff, pre-commit,
zensical and mkdocstrings.

Part of that is load-bearing: the tasks test tier (`cli/docker_task_tests.py`)
runs pytest inside each task image, so pytest and pytest-asyncio have to be
there. The rest (ruff, pre-commit, zensical, mkdocstrings) is dead weight in
every task, app and notebook image.

One shape: split the test runner into its own `test` group, sync images with
`--no-dev --group test` (or only the task images, if the app images don't run
tests), and keep `dev` for the local tools. Measure the image size difference
before deciding it's worth it.

Found while adding the diagram tooling (ticket `import-layers-diagrams`), which
went into its own `diagrams` group instead of `dev` for this reason.

## Outcome

Shipped in PR #98 (merge `eaa6d4d`): `gatk_env` and `scrna_env` images sync with `--no-dev`, and the tasks tier installs `pytest` and `pytest-asyncio` at their locked versions in each throwaway container rather than in the image. Measured on local linux/amd64 builds: gatk 110 → 77 packages, 3230 → 3031 MB; scrna 161 → 128, 2403 → 2204 MB. Tasks tier: gatk 39 passed, scrna 18 passed; unit tier 560 passed. Left: the dashboard image still installs the dev group, ticket `dashboard-image-no-dev`. No review comments.
