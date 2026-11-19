---
title: split-config
status: review
priority: low
created: 2026-11-16
pr: 169
---

`src/stargazer/config.py` (334 lines on `main`, 2026-11-16) does five jobs: the env var defaults, the logger, `init_flyte()`, the image recipes (`task_image`, `notebook_image`, `_with_sdk`, the header regex) and `log_execution()`. Its docstring lists them. Importing it for a logger pulls in `flyte` and the image code.

## Plan

- [x] The image recipes move to `stargazer/images.py`, with `IMAGE_PLATFORM`, `_checkout()` and `PROJECT_ROOT`. `config.py` keeps the defaults, the forwarded variables and secrets, the logger and `init_flyte()`. Infra imports some of these names, so the move lands with its pin bump.
- [x] `log_execution()` is dropped, with its call sites (settled with the user, 2026-11-19). It was asked for in ticket [[robust-logging]] (one logfile per workflow execution). What it does today: reads the caller's name from the frame, shells out to `git` twice, and adds a log sink. In a task pod there is no repository, so the commit is `unknown` (inferred from the image having no `.git`; not checked in a pod), and the file is on a disk that goes with the pod. A run's record is Flyte's.
- [x] Docs: `docs/architecture/configuration.md`, each moved function's `spec:` line, `docs/reference/api.md`.
- [ ] At the next release, two other repos import a moved name from `stargazer.config` and need a one-line repoint: infra's `app/admin_app.py` (`IMAGE_PLATFORM`, with the pin bump) and community-notebooks' `scrna/clustering-pipeline.py` (`notebook_image`).

## Verification recipe

```bash
pixi run pytest -q                                   # unit tier
pixi run python cli/docker_task_tests.py             # tasks tier, every image
pixi run python -I -c "import stargazer.images"      # no import cycle
pixi run python -I -c "import stargazer.config"
```

To confirm the images are unchanged, build `task_image()` for each domain and `notebook_image()` for the template, on `main` and on the branch, and diff their layers except `CopyConfig`. Only the `.dockerignore` layer's absolute path may differ.

Related: [[board]], [[bare-task-environments]], [[robust-logging]].
