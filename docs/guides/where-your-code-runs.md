# Where Your Code Runs

1. **Every SDK task runs in its domain's environment, wherever it runs.** It's declared once, in the header of `tasks/<domain>/env.py`. The cluster runs it as the task image, docker runs that image, and *On this machine* installs the same header and lock.
2. **A notebook's kernel is its header.** marimo writes it as you import. List what your cells use, nothing else.
3. **Calling an SDK task from a notebook needs nothing in your header.** *On this machine* runs it in its own environment on your machine, not in your kernel; *On the cluster* runs it in its task image.
4. **Your notebook's own tasks run in your notebook's environment.** *On this machine*, in your kernel; on the cluster, in an image built from your notebook's header, so what you installed while experimenting is what the cluster gets.

So the SDK's tasks bring their own environment, and a notebook's tasks use the notebook's. In both cases one header lists a task's packages and builds its image, so the two can't drift.

## Your notebook's header

A notebook that analyzes scRNA-seq data with the SDK's tasks and plots the result lists only what its cells import:

```python
# /// script
# requires-python = ">=3.14"
# dependencies = ["marimo", "stargazer-bio", "matplotlib"]
#
# [tool.pixi.dependencies]
# python = "3.14.*"
# ///
```

scanpy isn't there: `normalize` and the rest of the scRNA tasks bring it with them. A tool your own cells call, say `bcftools`, goes under `[tool.pixi.dependencies]`, with bioconda in `[tool.pixi.workspace]`'s channels.

## On this machine

The switch from `run_location()` decides where `dispatch` runs a task (the Execution tutorial walks through both). *On this machine* runs:

- **An SDK task** in its domain's environment. pixi installs the domain's header and lock the first time a task needs it, under your local scratch space (`STARGAZER_LOCAL`, see [Configuration](../architecture/configuration.md#environment-variables)), and reuses it after. The scRNA environment takes about a minute to install the first time. The task imports the same `stargazer` as your notebook, so an edit in your checkout shows up in its next run. Where a domain's header doesn't list your platform, docker runs the task in its task image instead.
- **An SDK workflow** in your notebook's process, with each task it calls in that task's own environment. One workflow can call gatk's tasks and scRNA's.
- **Your notebook's own tasks** in your kernel, with whatever your header installed.

A hosted notebook works the same way: its pod installs the domain environments with pixi.

## On the cluster

Every task runs in a pod of its own, on its environment's image. An SDK task's image is built from its domain's header and lock, with the SDK your run was submitted with on top.

## At your own risk

These work, but the guarantees above don't cover them:

- **Any other image** on your notebook's own `TaskEnvironment`, such as `core_image(...)` with layers added, or `flyte.Image.from_base`.
- **Domain packages in your header**, to call an SDK task's code directly in your kernel.
- **An unlocked notebook header.** Its cluster image can resolve differently from one build to the next, so the header alone doesn't pin what a run gets.
