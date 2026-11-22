---
title: images-repoint
status: review
priority: normal
created: 2026-11-21
pr: 50
---

Ticket [[split-config]] moved the image recipes from `stargazer.config` to `stargazer.images`. Two other repos still import a moved name from `stargazer.config` and break on the first release after `v2026.11.18.1`: infra's `app/dashboard.py` (`IMAGE_PLATFORM`), which lands with its `stargazer-bio` pin bump, and community-notebooks' `scrna/clustering-pipeline.py` (`notebook_image`). Each is a one-line repoint to `stargazer.images`, checked by importing the module against the new release.

## Plan

- [x] A release carrying the move: stargazer PR 173 released `2026.11.22` (package and image published 2026-11-22; the docs deploy on the same push failed to find its artifact and passed on a rerun).
- [x] infra PR 50: pins `stargazer-bio==2026.11.22`, takes `IMAGE_PLATFORM` from `stargazer.images`, and drops the dead `NOTEBOOK_KEY` skip in `/assets/schema`. Unit tier 447 passed on the release; with the old import it failed to collect. On the tenant, the test account's dashboard served `2026.11.22-10dcfd0`, its schema had no `notebook`, and the Assets tutorial launched on `v2026.11.22`'s digest (`bc208573…`) and ran all 22 cells with no error (measured 2026-11-22).
- [x] community-notebooks PR 8: the scRNA pipeline takes `notebook_image` from `stargazer.images` (`7da2ad2`), and its catalog entry moves to that commit. Against `stargazer-bio==2026.11.22` from PyPI, `main`'s version fails to import and the branch's imports; the germline notebook imports too (measured). It merges after infra PR 50 and its `stargazer-users upgrade`, since the new entry doesn't import on 2026.11.18.1.

## Verification recipe

1. Import each notebook against the release: `uv run --isolated --no-project -p 3.14 --with stargazer-bio==<version> --with marimo python -c '<load the file with importlib>'`; importing runs its setup block.
2. In infra's worktree, `uv run pytest` on the new pin.
3. `union_dashboard.py deploy`; the dashboard's footer shows the release; `POST /launch` `slug=assets mode=edit section=tutorials`; `union_dashboard.py check nb-assets-edit` serves the release tag's digest (`docker buildx imagetools inspect`); run all cells in the editor, none errors.
4. `union_dashboard.py teardown`; live runs `[]`.

Related: [[board]], [[split-config]], [[infra-sdk-pin-bump]].
