---
title: Task images carry the whole dev group
status: maybe
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
