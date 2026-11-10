# Task Model

Tasks are async Flyte v2 functions that perform a single bioinformatics operation. Each task receives typed `Asset` inputs, fetches them to disk, runs a tool against their paths, and stores its outputs as new assets via `store()`, writing them into the asset graph. For the full pattern with code, see [Writing a Task](../guides/writing-a-task.md).

## Conventions

- One task per function, one function per operation
- An output records the assets it was made from in `<asset>_cid` fields, so the asset graph can be queried for lineage
- Task files live in a domain subdirectory of `src/stargazer/tasks/` (`gatk/`, `general/`, `scrna/`), one file per tool
- Async is preferred for I/O operations
- Each task runs on a `TaskEnvironment` from its domain's `env.py` — `gatk_env` (GATK, BWA, BWA-MEM2, samtools; `general/` shares it) or `scrna_env` (scanpy) — whose image carries its tool and which sets its resources. A domain's packages import inside the task bodies, so importing a task needs only the core
- Outputs are written to a fresh scratch directory per task, so samples run side by side don't collide

## Available Tasks

The MCP registry and the [Catalog](../reference/catalog.md#tasks) list the tasks `stargazer.tasks` exports.
