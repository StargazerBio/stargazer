# Stargazer wiki

The agents' knowledge of what Stargazer builds on: Flyte, marimo and the bioinformatics tools its tasks wrap. Pages are synthesized from the raw sources in `raw/`, link each other with `[[wikilinks]]`, and point into Stargazer's code under "In Stargazer". Stargazer's own internals aren't here: they're in the docstrings and comments of the code they describe, and `docs/architecture/`. The `wiki` skill says how to read, add to and check it.

## Flyte v2

- [[flyte]]: the v2 model (workflows are tasks calling tasks), running tasks, and the features Stargazer doesn't use yet
- [[flyte-config]]: the config file and its search order
- [[flyte-task-environments]]: the three configuration levels, resources, environments that depend on each other
- [[flyte-images]]: how a `flyte.Image` is declared and built
- [[flyte-concurrency]]: parallel task calls with `asyncio.gather`
- [[flyte-io]]: what crosses a task boundary by value and what by reference
- [[flyte-caching]]: cache behaviors, versions and overwrites
- [[flyte-errors]]: retries, timeouts, and catching a failed task call
- [[flyte-apps]]: long-running services, which every notebook pod is

## marimo

- [[marimo-sandbox]]: a notebook's PEP 723 header and the venv built from it

## Bioinformatics tools

- [[tool-help]]: the captured help of the tools tasks wrap, and how to capture more
- [[gatk]]: GATK tools and the task that wraps each
- [[parabricks]]: NVIDIA's GPU equivalents, which no task wraps

## Raw sources

Kept as captured, never edited; pages cite them in their `sources`.

- [[flyte-v2-docs]]: the Flyte 2 docs, from its beta: overview, setup, task configuration, images, retries, I/O, tutorials
- [[flyte-sdk-examples]]: a digest of the Flyte 2 SDK examples, one section per feature
- [[marimo-inlining-dependencies]]: marimo's guide to sandboxed notebooks and PEP 723 headers
- `raw/tool-help/`: tool help and manuals, one file per command, listed on [[tool-help]], [[gatk]] and [[parabricks]]
