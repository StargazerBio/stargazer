# Task Model

Tasks are async Flyte v2 functions that perform a single bioinformatics operation. Each task receives typed `Asset` inputs, fetches them to disk in parallel, runs a tool against their paths, and registers its outputs as new assets via `update()`. For the full pattern with code, see [Writing a Task](../guides/writing-a-task.md).

## Conventions

- One task per function, one function per operation
- Task files live in `src/stargazer/tasks/`, named by tool or domain
- Async is preferred for I/O operations
- Resource requests (CPU, memory, GPU) are specified via `TaskEnvironment`

## Available Tasks

See the [Catalog](../reference/catalog.md#tasks) for a complete list of registered tasks.
