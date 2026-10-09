# Task Model

Tasks are async Flyte v2 functions that perform a single bioinformatics operation. Each task receives typed `Asset` inputs, fetches them to disk, runs a tool against their paths, and stores its outputs as new assets via `update()`. For the full pattern with code, see [Writing a Task](../guides/writing-a-task.md).

## Conventions

- One task per function, one function per operation
- Task files live in a domain subdirectory of `src/stargazer/tasks/` (`gatk/`, `general/`, `scrna/`), one file per tool
- Async is preferred for I/O operations
- Each task runs on a `TaskEnvironment` from `config.py` — `gatk_env` (GATK, BWA, BWA-MEM2, samtools) or `scrna_env` (scanpy) — whose image carries its tool and which sets its resources
- Outputs are written under the storage client's local directory, named after their sample, so samples run side by side don't collide

## Available Tasks

The MCP registry and the [Catalog](../reference/catalog.md#tasks) list the tasks `stargazer.tasks` exports.
