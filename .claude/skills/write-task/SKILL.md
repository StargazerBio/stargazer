---
name: write-task
description: "Implement a Stargazer Flyte v2 task that wraps a bioinformatics tool: where it goes, its TaskEnvironment and image, the task template, docstrings and exports. Use when adding or changing anything in src/stargazer/tasks/."
---

# Write a task

A task is a single-purpose Flyte v2 task that wraps one bioinformatics tool.

## Core Principles

1. **One Task, One Purpose**: Each task should do exactly one thing well
2. **Async by Default**: Use async tasks for I/O-heavy bioinformatics operations
3. **Structured I/O**: Use dataclasses from `src/stargazer/assets/` for inputs/outputs
4. **Resource Specification**: Define appropriate CPU, memory, and GPU requests
5. **Type Safety**: Use proper type annotations throughout

## Implementation Process

When implementing a task:

1. **Research First**:
   - The `tool-refs` skill has the tool's help text, the source of truth for its parameters
   - The `flyte-v2` skill has the SDK's docs and examples
   - Look at existing tasks in `src/stargazer/tasks/` for established patterns

2. **Define Types**:
   - Create or update `Asset` subclasses in `src/stargazer/assets/`, every field with a default
   - Use descriptive names (e.g., `Alignment`, `Variants`)
   - Import Flyte I/O types from `flyte.io` (NOT flytekit!)

3. **Implement Task**:
   - Place in the domain subdirectory of `src/stargazer/tasks/` (`gatk/`, `general/`, `scrna/`), one file per tool
   - Use naming pattern: `{action}_{tool}` or the tool's own verb (e.g. `bwa_mem`, `sort_sam`, `haplotype_caller`)
   - Decorate with the `TaskEnvironment` whose image carries the tool (`gatk_env` or `scrna_env` in `config.py`); resources are set there, not per task
   - Check the tool is on that env's image (`with_apt_packages`, `with_commands`, or the bioconda block); add it and say so if it isn't
   - Follow async/await patterns
   - Use pathlib.Path for filesystem operations; `_run` converts arguments to str at the subprocess boundary
   - Export the task from `src/stargazer/tasks/__init__.py` (`__all__`), which the MCP registry and the catalog read

4. **Document**:
   - Module docstring: a `###` heading first, a `spec: [docs/architecture/tasks.md](../architecture/tasks.md)` line last
   - Include comprehensive docstring explaining purpose
   - Document all parameters and return values
   - Include reference URLs for the tool
   - List output files created

## Task Template

```python
# src/stargazer/tasks/{domain}/{tool}.py
"""
### {Tool} task for Stargazer.

{What the tool does, in a sentence.}

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

import stargazer.utils.storage as _storage
from stargazer.assets import {InputType}, {OutputType}
from stargazer.config import gatk_env, logger  # or scrna_env for scRNA tasks
from stargazer.utils import _run


@gatk_env.task
async def {action}_{tool}(input_data: {InputType}) -> {OutputType}:
    """
    {Brief description of what this task does}.

    {Detailed explanation of the operation}

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

## Key Imports

```python
import stargazer.utils.storage as _storage   # default_client.local_dir for outputs
from stargazer.assets import {YourTypes}
from stargazer.config import gatk_env, logger  # or scrna_env
from stargazer.utils import _run               # Subprocess helper
```

## Resources

Resources live on the `TaskEnvironment` in `config.py`, shared by every task on it. The devbox node has ~7.75 GiB allocatable and a workflow's pods must fit together in ~6 GiB (the header of `devbox/setup.sh`), so a task's limit has to fit beside its workflow's parent task.

## File Organization

- **Domain subdirectories**: `gatk/`, `general/`, `scrna/`
- **One file per bioinformatics tool**, e.g. `general/bwa.py`, `gatk/sort_sam.py`
- **Multiple related tasks** can share a module (`bwa_index` and `bwa_mem`)

## Style Requirements

1. Use pathlib.Path for filesystem operations
2. Only convert Path to str immediately before subprocess calls
3. Use resolve() to get absolute paths when appropriate
4. Prefer async/await over sync operations
5. No TYPE_CHECKING blocks - Flyte always checks types

## Testing

Tests come first, with the `write-tests` skill, and run in the task's image (the tasks tier). Validate inputs at the start of the task, with error messages that say what to fix.

## Don't

- Don't use flytekit imports (use flyte.io instead)
- Don't copy v1 syntax directly - adapt to v2 patterns
- Don't add unnecessary complexity - handle one case well first
- Don't use relative imports across packages - use `from stargazer.{module}`
- Don't use TYPE_CHECKING blocks

## Report

Name the types created or changed, any resources or image changes, and decisions that need review.
