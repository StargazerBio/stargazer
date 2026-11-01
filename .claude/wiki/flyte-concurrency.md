---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/workflows/germline_short_variant_discovery.py
---

# Flyte concurrency

Parallelism in Flyte v2 is Python's own. Source: [[flyte-sdk-examples#6. Concurrency Patterns]].

- **`asyncio.gather` over task calls** runs them in parallel, each in its own container. Building the coroutines doesn't start them; `asyncio.create_task` does, immediately.
- **`flyte.map(task, items)`** is the sync form: a parallel `map` over a sync task.
- **Fan-out, then fan-in**: gather the calls, then aggregate their results in the calling task.
- **Bounded concurrency** is an `asyncio.Semaphore` around each call.
- **Cancelling** pending calls is cancelling their asyncio tasks ([[flyte-errors]]).
- **Batches** can be wrapped in `flyte.group(...)` to label them in the UI; see [[flyte-sdk-examples#Auto Batcher]].

## In Stargazer

- **Workflows gather per-sample and per-step calls.** `germline_short_variant_discovery` gathers each sample's preprocessing, then each sample's `haplotype_caller`, before joint calling. Read it for the house pattern before writing a workflow.
- **Every task is `async def`**, so `asyncio.gather` is the one form used; `flyte.map` appears nowhere.

## Related

- [[flyte]]: tasks calling tasks
- [[flyte-task-environments]]: what each parallel container is sized to
