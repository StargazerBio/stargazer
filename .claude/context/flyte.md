---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/config.py
  - pyproject.toml
---

# Flyte v2

The orchestrator every Stargazer task and workflow runs on. The raw sources are a snapshot of the Flyte 2 docs from its beta ([[flyte-v2-docs]]) and a digest of its SDK examples ([[flyte-sdk-examples]]); `pyproject.toml` pins the `flyte` package Stargazer actually runs, and the installed package wins where they disagree.

## The model

- **There is no `@workflow`.** A workflow is a task that calls other tasks. Tasks are plain Python functions decorated with `@env.task`, where `env` is a `TaskEnvironment` grouping their image, resources, env vars and secrets ([[flyte-task-environments]]).
- **Each task call runs in its own container**, configured by its environment. Tasks on one environment share a configuration, not a container.
- **Control flow is plain Python.** Loops and `asyncio.gather` replace `map` and `@dynamic` ([[flyte-concurrency]]); `if` replaces `conditional`; `try`/`except` replaces `on_failure` and can retry a task with more resources ([[flyte-errors]]).
- **Sync or async.** Async is preferred for I/O; Stargazer's tasks and workflows are all `async def`.
- **`@flyte.trace`** checkpoints a function inside a task, so a failed run replays from where it left off. See [[flyte-v2-docs#Fine-grained Reproducibility and Recoverability]].
- **The v1 to v2 mapping** is tabled in [[flyte-v2-docs#Simplified API]] and [[flyte-sdk-examples#19. Migration from v1]]. Never import `flytekit`.

## Running tasks

- **`flyte.run(task, **inputs)` runs remotely** by default; `flyte.with_runcontext(mode="local").run(...)` runs in the current process. `with_runcontext` also takes env vars, labels, `overwrite_cache` and more. The run's `url`, `wait()` and `outputs()` follow it. See [[flyte-sdk-examples#Running Tasks]].
- **`flyte.deploy(env)` deploys** an environment's tasks, apps and triggers without running them; the CLI's `flyte run` and `flyte deploy` mirror the SDK.
- **A deployed task can be called from another run** through `flyte.remote.Task.get(...)`.
- **Init first.** Stargazer's one init is `init_flyte()` in `config.py`: an in-cluster client in a hosted notebook pod, the config file anywhere else ([[flyte-config]]).

## Concepts

- [[flyte-config]]: the config file, its search order, inline init
- [[flyte-task-environments]]: the three configuration levels, resources, environment dependencies
- [[flyte-concurrency]]: parallel task calls
- [[flyte-io]]: what's materialized and what's passed by reference
- [[flyte-caching]]: cache behaviors and versions
- [[flyte-errors]]: retries, timeouts and catching task failures
- [[flyte-apps]]: long-running services
- [[flyte-images]]: how a `flyte.Image` is declared and built

## Features Stargazer doesn't use yet

Covered only in the raw sources:

- **Groups** organize traces in the UI: [[flyte-sdk-examples#11. Traces & Groups]]
- **Reports**, HTML in the run's UI: [[flyte-sdk-examples#12. Reports]]
- **Triggers**, scheduled runs: [[flyte-sdk-examples#13. Triggers (Schedules)]]
- **Plugins** for Spark, Ray, Dask and PyTorch: [[flyte-sdk-examples#15. Plugins]]
- **Reusable environments** (actors), warm containers: [[flyte-sdk-examples#10. Reusable Tasks (Actors)]]
- **DataFrames** passed by reference: [[flyte-v2-docs#DataFrames]]

Secrets Stargazer does use: `config.py`'s `STARGAZER_SECRETS` declares `PINATA_JWT` (and the project's API key, when set) as a `flyte.Secret` on every environment. The forms are in [[flyte-sdk-examples#14. Secrets]].
