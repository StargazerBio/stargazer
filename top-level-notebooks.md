---
title: The scRNA notebook moves to a top-level notebooks folder
status: next
priority: normal
created: 2026-10-17
blocked_by:
  - devbox-postgres-index
  - production-context-files
---

Notebooks that aren't SDK tutorials live in the repo, in a top-level
`notebooks/` folder, where GitHub shows them and pull requests review them.
Reimplementations of papers are what it's for, and they'll be added as they
come. The scRNA notebook is the first to move. The workspace seeds move to
`app/`, which leaves `stargazer.notebooks` with the tutorials and
`notebook_base`.

Blocked by `save-whole-workspace` only because that branch rewrites the same
dashboard code and docs.

## Decided

2026-10-17:

- **Repo notebooks aren't assets.** GitHub already makes them public, so
  nothing publishes them. Publish in ticket `public-notebooks` is for
  workspace notebooks.
- **They don't ride in the notebook image.** The image copies only `src/` and
  `app/` (`app/per_notebook.py`), so a commit to a notebook in `notebooks/`
  doesn't rebuild it. Bringing one into a pod is ticket `open-from-github`.
  Until then the scRNA notebook runs from a checkout, not from the dashboard.
- **They aren't packaged.** `packages.find` includes only `stargazer*` and
  `app*`, so `notebooks/` stays out of the wheel.
- **The tutorials stay in the SDK**, in the image, under the dashboard's
  Tutorials section. They teach the SDK, so they ship from the same commit as
  the pod's SDK, and they keep importing each other as
  `stargazer.notebooks.tutorials.*`.
- **`notebook_base` stays** in `stargazer.notebooks`, since `main_img`
  expressions import it in the notebook's kernel.
- **The seeds go to `app/`.** Only the dashboard uses them, and their PEP 723
  header points `stargazer` at `/stargazer`, the pod's layout.

## Pieces

- [ ] Move `src/stargazer/notebooks/workflows/scrna_pipeline.py` to
      `notebooks/scrna_pipeline.py` and delete the `workflows/` package.
      Extend the `__marimo__/` line in `.gitignore` and the `B018` per-file
      ignore in `pyproject.toml` to `notebooks/`.
- [ ] Smoke test: `tests/notebooks/test_notebook_smoke.py` finds notebooks
      through the package, so it also loads `notebooks/*.py` by path. Check:
      `pytest --collect-only tests/notebooks` lists the scRNA notebook.
- [ ] Seeds: `src/stargazer/notebooks/workspace/` moves to `app/seeds/`, and
      `seed_source` in `app/notebooks.py` reads from there. The folder needs
      an `__init__.py` or a package-data entry to reach the dashboard image.
      The dashboard's GitHub link to `template.py`
      (`app/templates/dashboard.html`) and the seed tests in
      `tests/unit/test_app.py` follow it.
- [ ] Dashboard: the scRNA entry in `NOTEBOOKS` and the `workflows` section in
      `app/notebooks.py`, the Workflows section and Copy to workspace in the
      dashboard, and their tests in `tests/unit/test_app.py`.
- [ ] `docs/reference/api.md` drops `stargazer.notebooks.workflows.scrna_pipeline`.
      The `scrna-pipeline` feature in `verify-stargazer` uses the new path.
- [ ] Docs:
  - `docs/architecture/notebook.md`: the types table (Workflows leave the
    dashboard), the Analyst archetype, Workflow graduation (a PR into
    `notebooks/`, with no tile and no image release), Copy to workspace, and
    adding notebooks
  - `docs/architecture/overview.md`: the dashboard's notebook types
  - `.opencode/reference/architecture/app_internals.md`: the seeds' path,
    Copy, and the tile registry
- [ ] Verify on Union with the test account: the dashboard shows Tutorials and
      Workspace and no Workflows, and New with each seed creates a notebook
      with that seed's source. Run the `scrna-pipeline` feature from the new
      path. `uv build --wheel` holds no scRNA notebook and no `notebooks/`.
      Stop every app the check started.
