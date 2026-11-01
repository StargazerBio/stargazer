---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/config.py
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
- **`env.clone_with(name=..., ...)`** copies an environment with changes. A notebook's `main_env` is a `clone_with` of `notebook_env`.
- **`reusable=flyte.ReusePolicy(...)`** keeps containers warm between calls; see [[flyte-sdk-examples#10. Reusable Tasks (Actors)]].

## In Stargazer

- **The environments are in `config.py`** (`gatk_env`, `scrna_env`), with comments on how each is sized and built ([[flyte-images]]). The rules for adding one, and the devbox's memory budget, are in `AGENTS.md`.

## Related

- [[flyte-concurrency]]: calling tasks in parallel
- [[flyte-errors]]: `retries`, `timeout`, and overriding resources after a failure
