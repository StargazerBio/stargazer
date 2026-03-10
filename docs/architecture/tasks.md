# Task Model

Tasks are async Flyte v2 functions that perform a single bioinformatics operation. Each task receives typed `Asset` inputs, fetches them to disk, runs a tool, and produces new assets.

## Pattern

```python
@tool_env.task
async def my_task(ref: Reference, aln: Alignment) -> Variants:
    await asyncio.gather(ref.fetch(), aln.fetch())
    # ... run tool using ref.path, aln.path ...
    vcf = Variants()
    await vcf.update(output_path, sample_id="NA12878")
    return vcf
```

## Conventions

- One task per function, one function per operation
- Task files live in `src/stargazer/tasks/`, named by tool or domain
- Async is preferred for I/O operations
- Resource requests (CPU, memory, GPU) are specified via `TaskEnvironment`

## Available Tasks

{{ catalog }}
