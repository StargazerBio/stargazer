# Stargazer wiki

The agents' knowledge base: how Stargazer's subsystems work beneath `docs/architecture/`, and the frameworks and tools it builds on. Pages are synthesized from the raw sources in `raw/` and from the code, and link each other with `[[wikilinks]]`. The `wiki` skill says how to read, add to and check it.

## Stargazer

- [[runtime]]: the notebook pod beneath `docs/architecture/runtime.md`: `fserve`, a pod that hydrates and saves itself, the release image
- [[notebooks]]: dispatch, packaging, `main_env` and workspace copies, beneath `docs/architecture/notebook.md`
- [[storage]]: `_owner` stamping and the public tier, beneath `docs/architecture/configuration.md`
- [[provenance]]: the fields that tie an asset to the inputs it came from
- [[images]]: every image Stargazer runs on, and how Flyte builds them

## Flyte v2

- [[flyte]]: the v2 model (workflows are tasks calling tasks), running tasks, and the features Stargazer doesn't use yet
- [[flyte-config]]: the config file, its search order, and Stargazer's two configs and one init
- [[flyte-task-environments]]: the three configuration levels, resources, and `gatk_env` and `scrna_env`
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
