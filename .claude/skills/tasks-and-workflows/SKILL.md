---
name: tasks-and-workflows
description: "Write or change any Stargazer task or workflow: where it lives, its TaskEnvironment and image, assets as I/O, async composition with assemble() and asyncio.gather, docstrings and exports. Use when adding or changing anything in src/stargazer/tasks/ or src/stargazer/workflows/."
---

# Tasks and workflows

A task wraps one bioinformatics tool and does one thing. A workflow composes tasks into a pipeline, and in Flyte v2 it is itself a task, so the rules below hold for both. The Stargazer MCP server's `list_tasks` lists every task and workflow with its signature; read the closest existing one in `src/stargazer/tasks/` or `src/stargazer/workflows/` before writing another.

## Before writing

- The agent wiki (`.claude/context/`, the `wiki` skill) has the help text of the tools tasks wrap, the source of truth for their parameters (its `tool-help` and `gatk` pages), and the Flyte v2 SDK (its `flyte` page and the pages it links)
- Tests come first, with the `write-tests` skill

## Both

1. **Async, on a TaskEnvironment.** Every task and workflow is an `async def` decorated with a `TaskEnvironment` from `config.py` (`gatk_env` or `scrna_env`). Resources are set on the environment, shared by every task on it, not per task. The devbox node has ~7.75 GiB allocatable and a workflow's pods must fit together in ~6 GiB (the header of `devbox/setup.sh`).
2. **Assets for I/O.** Inputs and outputs are `Asset` subclasses from `src/stargazer/assets/`, every field with a default.
3. **Imports.** `import flyte` and `flyte.io`, never `flytekit`; `from stargazer.<module>`, never relative; no `TYPE_CHECKING` blocks. There is no `@workflow` decorator.
4. **Paths.** `pathlib.Path` throughout; `_run` converts arguments to `str` at the subprocess boundary.
5. **Docstrings.** The module docstring opens with a `###` heading and ends with a `spec:` line (`docs/architecture/tasks.md` or `workflows.md`). The function docstring says what it does, its args and returns, and for a task the tool's reference URL.
6. **Exports.** Add it to `__all__` in `src/stargazer/tasks/__init__.py` or `src/stargazer/workflows/__init__.py`, which the MCP registry and the catalog read.

## Tasks

- **Where:** the domain subdirectory of `src/stargazer/tasks/` (`gatk/`, `general/`, `scrna/`), one file per tool. Related tasks can share a module (`bwa_index` and `bwa_mem`).
- **Name:** `{action}_{tool}` or the tool's own verb (`bwa_mem`, `sort_sam`, `haplotype_caller`).
- **Image:** the tool must be on the environment's image (`with_apt_packages`, `with_commands`, or the bioconda block). If it isn't, add it and say so.
- **Inputs:** validate them first, with errors that say what to fix. A missing input is never made up for by doing another task's work: raise, naming the task that produces it.

```python
# src/stargazer/tasks/{domain}/{tool}.py
"""
### {Tool} task for Stargazer.

{What the tool does, in a sentence.}

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

import stargazer.utils.storage as _storage
from stargazer.assets import {InputType}, {OutputType}
from stargazer.config import gatk_env, logger  # or scrna_env
from stargazer.utils import _run


@gatk_env.task
async def {action}_{tool}(input_data: {InputType}) -> {OutputType}:
    """
    {What this task does}.

    Args:
        input_data: {Description of input}

    Returns:
        {Description of output}

    Reference:
        {URL to tool documentation}
    """
    logger.info(input_data.to_dict())
    input_path = await input_data.fetch()  # local path, companions beside it

    output_dir = _storage.default_client.local_dir
    output_path = output_dir / f"{input_data.sample_id}_{tool}.{ext}"
    await _run(["{tool}", "-I", input_path, "-O", output_path], cwd=output_dir)
    if not output_path.exists():
        raise FileNotFoundError(f"{tool} did not create {output_path}")

    output = {OutputType}()
    await output.update(
        output_path,
        sample_id=input_data.sample_id,
        tool="{tool}",
        {input_key}_cid=input_data.cid,
    )
    logger.info(output.to_dict())
    return output
```

`update()` stores the file and sets `cid` and `path`; a task that returns an asset it never updated returns nothing anyone can fetch. Name outputs after the sample: samples fanned out in one process share `local_dir`.

## Workflows

- **Where:** one module per pipeline in `src/stargazer/workflows/`, named for the pipeline; related workflows can share a module.
- **Scalar inputs, asset outputs.** A workflow takes scalars (a build, sample IDs) and `assemble()`s its assets, so the MCP server and a test can run it by name. Call `assemble()` once per kind of input: every filter must match each asset returned, so a reference (`build`) and a sample's reads (`sample_id`) take separate calls.
- **Composition.** `await` dependent steps in order; `asyncio.gather()` independent ones, never dependent ones. Break a long pipeline into sub-workflows.
- **Testing:** say which tier can run it end to end (a GATK workflow needs the devbox).

```python
# src/stargazer/workflows/{pipeline_name}.py
"""
### {Pipeline name}.

This workflow chains together:
1. {Step 1 description}
2. {Step 2 description}

spec: [docs/architecture/workflows.md](../architecture/workflows.md)
"""

import asyncio

from stargazer.assets import {InputType}, {OutputType}
from stargazer.assets.asset import assemble
from stargazer.config import gatk_env, log_execution  # or scrna_env
from stargazer.tasks import {task1}, {task2}


@gatk_env.task
async def {pipeline_name}(build: str, sample_ids: list[str]) -> list[{OutputType}]:
    """
    {What the pipeline does}.

    Args:
        build: Reference genome build to assemble the inputs for
        sample_ids: Samples to run, in parallel

    Returns:
        {Description of workflow outputs}
    """
    log_execution()
    assets = await assemble(build=build, asset="{input_key}")
    inputs = [a for a in assets if isinstance(a, {InputType})]
    if not inputs:
        raise ValueError(f"No {input_key} found for build={build!r}")

    prepared = await {task1}(inputs[0])
    return list(
        await asyncio.gather(*[{task2}(prepared, sample_id=s) for s in sample_ids])
    )
```

Run one from a script or a notebook: `flyte.with_runcontext(mode="local").run({pipeline_name}, build=..., sample_ids=[...])` in-process, or `flyte.run(...)` against the cluster `init_flyte()` (`stargazer.config`) points at. `.outputs()[0]` is the result.

## Report

Name the assets created or changed, any resource or image change, the parallelism, and decisions that need review.
