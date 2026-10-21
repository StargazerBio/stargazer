# Stargazer notebook

You're in the terminal of a Stargazer notebook: a container serving one user's marimo notebooks, either hosted (opened from their Stargazer dashboard) or run locally from the `stargazer` Docker image. Stargazer is a bioinformatics pipeline framework built on Flyte v2. Every file is a typed asset identified by its IPFS CID; tasks find their inputs by querying asset metadata, not by path.

## Where you are

- `/workspace`, your working directory, holds the user's notebooks side by side at the top, plus whatever files they keep beside them. It's theirs and there's no undo: ask before you delete or overwrite a file you didn't create, and treat their stored assets the same way.
- Hosted (`$STARGAZER_ADMIN_URL`, their dashboard, is set): every change in `/workspace` is saved to the user's storage within seconds, and a file deleted here is deleted there. Dotfiles, `__pycache__/`, `__marimo__/` and files over 100 MB aren't saved. Keep large data as an asset instead, then delete the file:
  `await default_client.upload(build_asset({"asset": "data"}), Path("/workspace/big.bam"))`, with `build_asset` from `stargazer.assets` and `default_client` from `stargazer.utils.storage`. Everything outside `/workspace` (your home directory, `/tmp`, anything you install) is gone when the notebook stops, which it does after 30 idle minutes.
- Local image: `/workspace` is usually a directory the user mounted from their machine, and assets live in `~/.stargazer`.
- `/stargazer` is the Stargazer SDK this image was built with, and every notebook installs it from there. Read it for reference: `src/stargazer/` for tasks, workflows and assets, `src/stargazer/notebooks/tutorials/` for worked notebooks. Don't edit it: an edit changes what every open notebook imports, and it's never saved.
- On PATH: `gatk`, `samtools`, `bwa`, `bwa-mem2`, `uv`, `marimo`.
- The editor doesn't reload an open notebook when its file changes on disk, and its own saves write its copy back over the file. Prefer new files (another notebook, or a module the notebook imports). Edit an open notebook's file only when the user asks, and tell them the editor shows the change only once the notebook is opened afresh (hosted: stop it and launch it again from the dashboard).

## marimo notebooks

- A notebook is a `.py` file: `app = marimo.App()`, then one `@app.cell` function per cell. A cell's parameters are the globals it reads and its returned tuple the globals it defines. Cells run in dependency order, not file order, and re-run when a cell they read from changes.
- Each global is defined in exactly one cell. Names starting with `_` are local to their cell. Don't mutate another cell's objects; marimo doesn't track mutation.
- A cell's last expression is its output: `mo.md(...)`, a `mo.ui` element, `mo.ui.table(...)`, a plot. Assign each `mo.ui` element (`mo.ui.file`, `mo.ui.dropdown`, `mo.ui.run_button`, ...) to a global and read its `.value` in another cell, never in the cell that made it. `mo.stop(condition, output)` halts a cell, e.g. until a file is uploaded.
- Cells can `await` at the top level.
- `with app.setup:` holds imports and definitions every cell can use. A cell holding just one function or class, decorated `@app.function` or `@app.class_definition` and using only setup-block names, is importable from the notebook like a module (`from other_notebook import fn`).
- Python packages go in the PEP 723 header (`# /// script`); each notebook runs in its own environment built from it at start. `stargazer` resolves to `/stargazer` through the header's `[tool.uv.sources]` entry; keep it.
- System tools go in the image the notebook runs on, declared in the setup block as `main_img = notebook_base.with_apt_packages(...)` (`from stargazer.notebooks import notebook_base`). It takes effect the next time the notebook launches from the dashboard. The line is evaluated on its own, so it can use only `flyte` and `notebook_base`.

## Task pattern

Tasks are async Flyte v2 functions that perform a single bioinformatics operation. Each task receives typed Asset inputs, fetches them to disk, runs a tool, and stores new assets.

```python
import asyncio

import stargazer.utils.storage as _storage
from stargazer.assets import R1, Alignment, Reference
from stargazer.config import gatk_env  # or scrna_env
from stargazer.utils import _run


@gatk_env.task
async def align_reads(ref: Reference, r1: R1) -> Alignment:
    """Align reads to a reference genome using BWA-MEM."""
    ref_path, r1_path = await asyncio.gather(ref.fetch(), r1.fetch())
    output_path = _storage.default_client.local_dir / f"{r1.sample_id}.sam"
    await _run(["sh", "-c", f"bwa mem {ref_path} {r1_path} > {output_path}"])
    result = Alignment()
    await result.update(output_path, sample_id=r1.sample_id, reference_cid=ref.cid)
    return result
```

- One task, one operation
- Always async, use asyncio.gather for parallel fetches
- fetch() returns the input's local path, with its companions (indexes, dictionaries) beside it; use that path, not asset.path (the stored file)
- Always update() outputs to store them; name output files after the sample
- Use pathlib.Path for filesystem ops; _run converts arguments to str for the subprocess
- Import from stargazer.assets, stargazer.config, stargazer.utils (never flytekit)
- No TYPE_CHECKING blocks — Flyte always checks types
- Resources (CPU, memory, GPU) and the image are set on the TaskEnvironment, not per task. `gatk_env` and `scrna_env` carry the SDK and its tools; a `flyte.TaskEnvironment` you define needs an image with everything its tasks import

## Asset types

Assets are dataclasses with typed fields, stored as flat keyvalues. Each subclass has a unique _asset_key, and every field needs a default.

```python
from dataclasses import dataclass
from typing import ClassVar

from stargazer.assets.asset import Asset


@dataclass
class MyOutput(Asset):
    _asset_key: ClassVar[str] = "my_output"
    sample_id: str = ""
    alignment_cid: str = ""
```

- Use descriptive names (Alignment, Variants, AnnData); the SDK's own are in `/stargazer/src/stargazer/assets/`
- A `<asset_key>_cid` field links an asset to the one it came from, and `assemble(<asset_key>_cid=...)` finds it. A file a tool needs beside its parent, like an index, gets a `companion_of` field set to the parent's CID instead; fetching the parent then brings it along
- Fields become keyvalues in storage — keep them flat strings/ints/bools

## Workflow pattern

Workflows are just tasks that call other tasks. No separate decorator.

```python
from stargazer.assets import R1, Alignment, Reference
from stargazer.assets.asset import assemble


@gatk_env.task
async def my_pipeline(build: str, sample_id: str) -> Alignment:
    """One-line description."""
    refs = await assemble(build=build, asset="reference")
    ref = next(a for a in refs if isinstance(a, Reference))
    reads = await assemble(sample_id=sample_id, asset="r1")
    r1 = next(a for a in reads if isinstance(a, R1))
    return await align_reads(ref=ref, r1=r1)
```

- Accept scalar parameters only (build, sample_id) — workflows call assemble() internally
- Every assemble() filter must match each asset it returns, so query a reference (build) and a sample's reads (sample_id) separately
- Filter assembled assets with isinstance, not string matching
- Use asyncio.gather for independent parallel tasks

## Running: local or on the cluster

The call site picks where a task or workflow runs; the code doesn't change.

- `await my_pipeline(...)` runs it in the notebook's own process, with no Flyte run record.
- `flyte.with_runcontext(mode="local").run(my_pipeline, build=..., sample_id=...)` runs it locally through Flyte's runtime (typed I/O, caching) and blocks; `.outputs()` holds the result.
- `flyte.run(my_pipeline, ...)` submits it to the backend `init_flyte()` (from `stargazer.notebooks`) connected to, which in a hosted notebook is the user's own project, and returns a run at once: `.url` links to the console, `.wait()` blocks, `.outputs()` holds the result. With no backend configured it runs in-process instead, and its `url` is a local path.
- `flyte.with_runcontext(mode="remote").run(...)` insists on the cluster: with no backend it raises instead of running locally.
- A cluster run imports the notebook in a fresh pod, which runs the setup block and the `@app.function` / `@app.class_definition` cells but not regular cells. So a task or workflow bound for the cluster, with its environment and asset types, has to be defined there; one defined in a regular cell can't be found. Its environment needs an image with whatever its module imports (stargazer, marimo); with none, the pod runs Flyte's base image.
- Wherever it runs, what a run stores lands in the user's storage and index, so `assemble()` finds it from the notebook afterwards.
