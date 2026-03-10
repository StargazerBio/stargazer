# Workflow Model

Workflows are tasks that compose other tasks into end-to-end pipelines. In Flyte v2, there is no separate `@workflow` decorator — workflows are regular tasks that call other tasks.

## Pattern

```python
@pipeline_env.task
async def my_workflow(build: str, sample_id: str) -> Variants:
    assets = await assemble(build=build, asset="reference")
    ref = next(a for a in assets if isinstance(a, Reference))
    # ... call tasks with ref, other typed assets ...
```

## Conventions

- Workflows accept scalar parameters and handle their own assembly via `assemble()`
- Workflow files live in `src/stargazer/workflows/`, named by analysis type
- Parallel execution uses `asyncio.gather`
- Workflows filter assembled assets with `isinstance` checks

## Available Workflows

{{ catalog }}
