---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
---

# Flyte errors

Retries, timeouts, and handling a failed task call in its caller. Sources: [[flyte-v2-docs#Retries and Timeouts]], [[flyte-sdk-examples#8. Error Handling]].

## Retries and timeouts

- **`retries=n`** on the decorator or an override allows `n` attempts after the first, so `retries=3` is up to four. It also takes a `RetryStrategy`.
- **`timeout`** is seconds, a `timedelta`, or `flyte.Timeout(max_runtime=..., max_queued_time=...)` to bound running and queueing separately. It combines with `retries`.

## Catching a failed call

- **A failed task call raises in its caller**, so `try`/`except` handles it like any Python error.
- **`flyte.errors.RuntimeUserError`** is what a task's own exception becomes; its `code` is the exception's class name (`"ValueError"`).
- **`flyte.errors.OOMError`** means the pod ran out of memory. The usual answer is calling again with more: `task.override(resources=flyte.Resources(memory=...))(...)`. A stepping retrier is [[flyte-sdk-examples#OOM Retrier]].
- **Cancelling** the remaining calls on a failure is cancelling their asyncio tasks before re-raising.
- **A circuit breaker** (stop after n failures) is [[flyte-sdk-examples#Circuit Breaker]].

## In Stargazer

- **No task sets `retries` or `timeout`.** A task that's missing an input raises, naming the input and the task that produces it, rather than retrying or doing that task's work.

## Related

- [[flyte-task-environments]]: where `retries`, `timeout` and resources can be set
- [[flyte-concurrency]]: the gathered calls a failure may need to cancel
