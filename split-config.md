---
title: split-config
status: backlog
priority: low
created: 2026-11-16
---

`src/stargazer/config.py` (334 lines on `main`, 2026-11-16) does five jobs: the env var defaults, the logger, `init_flyte()`, the image recipes (`task_image`, `notebook_image`, `_with_source`, `released_image`, the header regex) and `log_execution()`. Its docstring lists them. Importing it for a logger pulls in `flyte` and the image code.

## Plan

- [ ] The image recipes move to `stargazer/images.py`, with `IMAGE_PLATFORM`, `_checkout()` and `PROJECT_ROOT`. `config.py` keeps the defaults, the forwarded variables and secrets, the logger and `init_flyte()`. Infra imports some of these names, so the move lands with its pin bump.
- [ ] `log_execution()`: to settle with the user. It was asked for in ticket [[robust-logging]] (one logfile per workflow execution). What it does today: reads the caller's name from the frame, shells out to `git` twice, and adds a log sink. In a task pod there is no repository, so the commit is `unknown` (inferred from the image having no `.git`; not checked in a pod), and the file is on a disk that goes with the pod. A run's record is Flyte's. Either drop it and its five call sites, or keep it for local runs only.
- [ ] Docs: `docs/architecture/configuration.md`, each moved function's `spec:` line, `docs/reference/api.md`.

Related: [[board]], [[bare-task-environments]], [[robust-logging]].
