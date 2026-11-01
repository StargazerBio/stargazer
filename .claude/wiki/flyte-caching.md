---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/workflows/germline_short_variant_discovery.py
  - src/stargazer/workflows/scrna_clustering.py
---

# Flyte caching

Whether a task call reuses an earlier result. Source: [[flyte-sdk-examples#7. Caching]].

- **`cache` is set on the environment, the decorator or an override**, as a string or a `flyte.Cache` ([[flyte-task-environments]]).
- **`"auto"`** (or `Cache(behavior="auto")`) reruns only when the code or the inputs change.
- **`Cache(behavior="override", version_override="v2")`** reruns only when the version changes.
- **`ignored_inputs`** leaves named inputs out of the cache key.
- **`"disable"`** never caches.
- **`flyte.with_runcontext(overwrite_cache=True)`** reruns everything in that run and refreshes the cache.
- **`@flyte.trace`** adds checkpoints inside a task, finer than the task cache ([[flyte#The model]]).

## In Stargazer

- **Both workflows are `cache="disable"`**: `germline_short_variant_discovery` and `scrna_clustering`. Their tasks keep the environment's default.
