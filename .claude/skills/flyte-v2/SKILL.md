---
name: flyte-v2
description: The Flyte v2 SDK's documentation and a concise catalog of its example patterns (TaskEnvironment, images, resources, File/Dir I/O, concurrency, caching, retries, secrets, apps, triggers). Use when writing or debugging Flyte tasks, environments, images or runs, or when unsure how the v2 SDK does something.
---

# Flyte v2

Two references, each with a table of contents up top. Search them before reading them whole; they're long.

- [docs.md](docs.md): the Flyte 2 documentation: concepts, local setup, task configuration, container images, retries and timeouts, task programming.
- [examples.md](examples.md): the standard patterns and the full range of the SDK, distilled from its example files, by topic.

Flyte v2 is `import flyte`; nothing comes from `flytekit`. A workflow is a task that calls other tasks.
