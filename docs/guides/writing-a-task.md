# Writing a Task

This guide walks through adding a new bioinformatics task to Stargazer.

## 1. Define the Asset Type (if needed)

If your task produces a new kind of output, add an asset subclass to the matching module in `src/stargazer/assets/`:

```python
from dataclasses import dataclass
from typing import ClassVar

from stargazer.assets.asset import Asset


@dataclass
class MyOutput(Asset):
    """What the file is, in one line."""

    _asset_key: ClassVar[str] = "my_output"
    sample_id: str = ""
    alignment_cid: str = ""
```

The `_asset_key` must be unique, and every field needs a default: the base class's fields have them, and older records may lack a newer field. The class registers itself via `__init_subclass__` when its module is imported, so import it in `src/stargazer/assets/__init__.py` and add it to `__all__`. A `<asset_key>_cid` field such as `alignment_cid` records which asset this one came from, and makes it a companion: fetching that alignment brings this file along.

## 2. Create the Task Module

Add a file to the domain subdirectory of `src/stargazer/tasks/` (`gatk/`, `general/`, `scrna/`), named after the tool (e.g., `my_tool.py`):

```python
"""
### my_tool task for Stargazer.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

import asyncio

import stargazer.utils.storage as _storage
from stargazer.assets import Alignment, MyOutput, Reference
from stargazer.config import gatk_env, logger
from stargazer.utils import _run


@gatk_env.task
async def my_tool(ref: Reference, alignment: Alignment) -> MyOutput:
    """One-line description of what this task does."""
    ref_path, bam_path = await asyncio.gather(ref.fetch(), alignment.fetch())

    output_dir = _storage.default_client.local_dir
    output_path = output_dir / f"{alignment.sample_id}_my_tool.txt"
    await _run(["my_tool", "-R", ref_path, "-I", bam_path, "-O", output_path])
    if not output_path.exists():
        raise FileNotFoundError(f"my_tool did not create {output_path}")

    result = MyOutput()
    await result.update(
        output_path, sample_id=alignment.sample_id, alignment_cid=alignment.cid
    )
    logger.info(result.to_dict())
    return result
```

## 3. Key Rules

- **One task, one operation** — don't combine multiple tool calls unless there's a good reason, e.g. piping between tools where the intermediate would have little long-term value for re-analysis
- **Always `fetch()` inputs** — it returns the local path, with companions (indexes, dictionaries) in the same directory
- **Always `update()` outputs** to store them and record their metadata
- **Use `asyncio.gather`** to fetch multiple inputs in parallel
- **Write outputs under `_storage.default_client.local_dir`, named after the sample** — samples fanned out in one process share that directory, so a fixed filename lets them overwrite each other
- **Pick the environment whose image carries the tool** — `gatk_env` or `scrna_env` in `src/stargazer/config.py`, where resources are set too. A new tool goes onto that image (see [Configuration → Adding a tool](../architecture/configuration.md#adding-a-tool))
- **Use `pathlib.Path`** for all filesystem operations; `_run` converts its arguments to `str` for the subprocess

## 4. Register in the MCP Server

The MCP registry and the [Catalog](../reference/catalog.md) list the tasks `stargazer.tasks` exports. Import your task in `src/stargazer/tasks/__init__.py` and add it to `__all__`.

## 5. Test

Write its tests in `tests/tasks/<domain>/` and run them in the task's own image, where the tool is installed:

```bash
uv run --all-extras python cli/docker_task_tests.py tests/tasks/gatk/test_my_tool.py
```

Build inputs from the fixture files and call the `fixtures_db` checkout before the task, so its outputs land in an empty per-test store. Assert on the output's fields and file, not just its type. The patterns are in [`tests/TESTING_GUIDE.md`](https://github.com/StargazerBio/stargazer/blob/main/tests/TESTING_GUIDE.md).
