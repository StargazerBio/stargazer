---
title: pixi-development
status: backlog
priority: normal
created: 2026-11-03
blocked_by:
  - pixi-notebook-sandbox
---

Development runs under pixi, and `uv.lock` goes: contributor setup, the test tiers' commands, pre-commit and its pinned ruff, and the release workflow. Until then pixi.lock and uv.lock are separate resolutions that drift between relocks, and the Flyte SDK has to match between them by hand (the task images' base is tagged by the submitter's Flyte, their runtime is pixi.lock's). The third stage of [[pixi-dependencies]].

- A dev environment in `[tool.pixi.environments]` with the `dev` group, and `osx-arm64` in the workspace's platforms, so the tools can be on a contributor's machine too.
- The tiers' `uv run` commands, `cli/docker_task_tests.py`'s test packages (pinned from uv.lock today), pre-commit and `.github/workflows/release.yml` under pixi. Publishing `stargazer-bio` still needs a build backend to build the wheel.
- AGENTS.md, the `write-tests` skill and Contributing updated; the relock command in Contributing becomes plain `pixi lock`.

Related: [[board]], [[pixi-dependencies]], [[pixi-notebook-sandbox]].
