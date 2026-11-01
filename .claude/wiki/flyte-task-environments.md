---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/config.py
  - devbox/setup.sh
---

# Flyte task environments

A `TaskEnvironment` groups the configuration its tasks run with. Sources: [[flyte-v2-docs#Task Configuration]], [[flyte-sdk-examples#2. Task Environments & Resources]].

## Three levels of configuration

From most general to most specific, and the more specific wins:

1. **The `TaskEnvironment`**: `name` (required), `image`, `resources`, `env_vars`, `secrets`, `cache`, `pod_template`, `reusable`, `depends_on`, `description`, `plugin_config`.
2. **The `@env.task` decorator**: `short_name`, `secrets`, `cache`, `pod_template`, `report`, `max_inline_io_bytes`, `retries`, `timeout`, `docs`.
3. **`task.override(...)` at the call**: `short_name`, `resources`, `env_vars`, `secrets` (those three only on a non-reusable environment), `cache`, `reusable`, `max_inline_io_bytes`, `retries`, `timeout`.

**`image` is environment-only**, and `resources` and `env_vars` can't be set on the decorator. The full matrix is [[flyte-v2-docs#Parameter Overview]].

## Resources

- **`flyte.Resources`** takes `cpu`, `memory`, `gpu`, `disk` and `shm`. A tuple is a request and a limit: `memory=("1Gi", "6Gi")`.
- **`gpu`** names a type and count (`"A100 80G:1"`, `"T4:1"`), or a `flyte.TPU`. The accelerator list is in [[flyte-sdk-examples#2. Task Environments & Resources]].

## Between environments

- **`depends_on=[other_env]`** declares an environment this one's tasks call into, so its image is built first. An app environment can be one, so a task can call the app ([[flyte-apps]]).
- **`env.clone_with(name=..., ...)`** copies an environment with changes. A notebook's `main_env` is a `clone_with` of `notebook_env` ([[notebooks#main_env]]).
- **`reusable=flyte.ReusePolicy(...)`** keeps containers warm between calls; see [[flyte-sdk-examples#10. Reusable Tasks (Actors)]].

## In Stargazer

- **Two task environments, in `config.py`**: `gatk_env` (GATK, BWA, samtools) and `scrna_env` (scanpy). Every task is decorated with one of them. Their images are on [[images#The task images]].
- **Resources are set on the environment**, shared by every task on it, as a request and limit. They're sized for the devbox: its node has about 7.75 GiB allocatable and a workflow's pods must fit together in about 6 GiB (the header of `devbox/setup.sh`). `gatk_env` requests 1Gi because the germline workflow holds three of its pods at once.
- **Every environment forwards `STARGAZER_ENV_VARS` and declares `STARGAZER_SECRETS`.**
- **A workflow is a task on one of the same environments**, often with `cache="disable"` ([[flyte-caching]]).

## Related

- [[flyte-concurrency]]: calling tasks in parallel
- [[flyte-errors]]: `retries`, `timeout`, and overriding resources after a failure
