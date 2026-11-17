# Workflow Model

Workflows are tasks that compose other tasks into end-to-end pipelines. In Flyte v2, there is no separate `@workflow` decorator — workflows are regular tasks that call other tasks. A workflow accepts scalar parameters, looks up its typed inputs in the asset graph with each type's `find()`, and chains tasks against them. Because its inputs are metadata rather than files, it runs on any data that carries that metadata: the user's own, a bundle's or another user's published assets. For the full pattern with code, see [Writing a Workflow](../guides/writing-a-workflow.md).

## Conventions

- Workflows accept scalar parameters and look up their own inputs, one `find()` per input: the newest stored asset of that type matching every filter, or an error naming what's missing
- Workflow files live in `src/stargazer/workflows/`, named by analysis type
- Parallel execution uses `asyncio.gather`
- A workflow, not a task, decides whether work is needed: `prepare_reference` fetches the reference, which brings its companions with it, and builds only the indexes that didn't arrive, so an index built once, by the user or the reference's publisher, is reused

## Available Workflows

The MCP registry and the [Catalog](../reference/catalog.md#workflows) list the workflows `stargazer.workflows` exports. Notebooks can define their own workflows the same way; those run in the notebook and aren't registered.
