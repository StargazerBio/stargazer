# Workflow Model

Workflows are tasks that compose other tasks into end-to-end pipelines. In Flyte v2, there is no separate `@workflow` decorator — workflows are regular tasks that call other tasks. A workflow accepts scalar parameters, assembles its typed inputs via `assemble()`, and chains tasks against them. For the full pattern with code, see [Writing a Workflow](../guides/writing-a-workflow.md).

## Conventions

- Workflows accept scalar parameters and handle their own assembly via `assemble()`
- Workflow files live in `src/stargazer/workflows/`, named by analysis type
- Parallel execution uses `asyncio.gather`
- Workflows filter assembled assets with `isinstance` checks

## Available Workflows

See the [Catalog](../reference/catalog.md#workflows) for a complete list of registered workflows.
