---
title: pixi-dependencies
status: review
priority: normal
created: 2026-11-03
pr: 127
---

Manage Stargazer's dependencies with pixi instead of uv: one tool that installs conda packages (bioconda's tools, conda-forge's libraries) and PyPI packages into one locked environment, for notebooks, task images and development alike. Today Python packages are declared and locked (notebook headers, `pyproject.toml`, `uv.lock`), but command-line tools are not: `gatk_env` installs gatk4, samtools, bwa and bwa-mem2 from an unpinned `micromamba create` in a `with_commands` string, and since ticket [[warm-uv-cache]] a notebook that runs a tool in its own process (the community germline notebook on "On this machine") relies on the user running `micromamba install`.

## What exists (read 2026-11-03)

- **marimo's pixi sandbox** (marimo ≥ 0.25.0, so the 0.25.1 the image pins; [marimo.io/blog/pixi-sandboxes](https://marimo.io/blog/pixi-sandboxes), `marimo/_environments/pixi.py`): `--sandbox=pixi` builds a notebook's environment as a conda environment from its own header. PyPI packages stay in the standard PEP 723 `dependencies`; conda packages go under `[tool.pixi.dependencies]`, channels under `[tool.pixi.workspace]`. The package panel adds PyPI packages with `pixi add --script --pypi`; the kernel's `--with marimo` overlay rides uv through `pixi exec`, chaining the conda prefix.
- **pixi scripts** ([pixi docs, Standalone Scripts](https://pixi.prefix.dev/latest/python/scripts/)): `run`, `add`, `lock`, `update` with `--script`; an editable local project is `[tool.pixi.pypi-dependencies]` with `editable = true`; `pixi lock --script` writes `<script>.pixi.lock` beside it; a cached resolution isn't moved by new releases until `pixi update --script`. The docs both recommend `pixi install --script` for container builds and list `install` as workspace-only; Flyte's code says "Pixi has no `install --script`". Check against the pixi version we'd pin.
- **pixi projects** ([pyproject.toml](https://pixi.prefix.dev/latest/python/pyproject_toml/), [Conda & PyPI](https://pixi.prefix.dev/latest/concepts/conda_pypi/)): `pyproject.toml` with `[tool.pixi.workspace]` is a pixi manifest; `[project.dependencies]` become PyPI dependencies and optional-dependencies and dependency groups become features, one environment each, solved together into `pixi.lock`. Conda first, then PyPI through uv used as a library. Python itself comes from conda-forge. **`[tool.uv.sources]` in the main manifest is ignored**, so the notebook headers' `stargazer-bio = { path = "/stargazer", editable = true }` moves to `[tool.pixi.pypi-dependencies]`.
- **Flyte 2.10.7 images** (`flyte/_image.py`): `Image.with_pixi_project(manifest, pixi_lock=..., environment=...)` installs a pixi project (or `pyproject.toml`) environment and makes it the image's runtime; `Image.from_pixi_script(script, ...)` builds from a PEP 723 header including `[tool.pixi.*]`, using `<script>.pixi.lock` if present. Union's remote builder supports both: its IDL has no pixi layer, so Flyte lowers them to primitive layers (`_internal/imagebuild/remote_builder.py:268`). `flyte` must be in the environment, as a PyPI dependency: it isn't on conda-forge.
- **Availability** (anaconda.org API): conda-forge has Python 3.14 and marimo 0.25.1; bioconda has gatk4 4.6.2.0 (noarch), samtools 1.25 and bwa-mem2 2.3 for linux-64, linux-aarch64 and osx-arm64.

## What it would simplify

- **Task images from one manifest.** `gatk_env` and `scrna_env` become `with_pixi_project(pyproject.toml, environment="gatk" | "scrna")`, with gatk4 and friends as conda dependencies of a `gatk` feature and the `bio` extra as the `scrna` one. Tools get locked versions; the shell string in `config.py` goes.
- **Notebooks declare their tools.** A header lists `gatk4` beside `stargazer-bio`, and it installs wherever the notebook opens. The germline notebook needs no special handling, and ticket [[local-notebook-images]] mostly stops mattering.
- **Development.** The tools could be on a contributor's machine through the dev environment, on macOS too (inferred from bioconda's osx-arm64 builds; the tasks tier would still run in task images).

## Open questions

- Open and build times against uv: a core notebook, germline with gatk4 (a JVM), the task images. Whether the image can prewarm pixi's cache the way `/opt/uv-cache` is warmed, and what it adds.
- The `--with marimo` overlay over a conda prefix in our image, and PyPI packages layered on conda ones (pixi's conda-to-PyPI name mapping, fetched from conda-mapping.prefix.dev, so it needs network or a pinned local mapping).
- What changes for publishing `stargazer-bio` to PyPI (a build backend still builds the wheel; uv or `python -m build` under pixi), the release workflow, pre-commit and its pinned ruff, the test tiers' `uv run` commands, and AGENTS.md.
- Whether hosted notebook pods still need a declared `main_env` image for tools, or the header is enough.

## Plan

In stages, each shippable alone:

- [x] Task images: a `[tool.pixi]` section in `pyproject.toml` with `gatk` and `scrna` features, `pixi.lock`, and `gatk_env`/`scrna_env` built with `with_pixi_project`. Verify with the tasks tier and a germline run on the devbox. PR 127. Measured 2026-11-03: tasks tier 35 passed (images built locally in 8 min, emulated), devbox germline 2 passed in 2:19, Union remote builds 2:41 (gatk) and 0:53 (scrna) with a probe task succeeding on each. uv.lock moved to flyte 2.12.4 to match pixi's lock.
- [ ] Notebook sandbox: pixi in the image, `--sandbox=pixi` in the launch script, headers moved to `[tool.pixi.pypi-dependencies]` for the SDK, the warm cache redone for pixi. Verify a core notebook and the germline notebook (with its tools in its header) locally and hosted, timed against uv.
- [ ] Development: contributor setup, tests, pre-commit and release under pixi.

## Verification recipe: task images from pixi

`gatk_env` and `scrna_env` build their images from pixi.lock's `gatk` and `scrna` environments, and every task runs in them as before: the tools on PATH at their locked versions, the stargazer package importable, Flyte running the task.

### Sub-features

- `pixi-tasks-tier`: every task test passes in its pixi-built image.
- `pixi-tool-versions`: the gatk image's tools are the versions pixi.lock pins.
- `pixi-devbox-germline`: the germline workflow runs on the devbox, each step in a pod on the pixi-built gatk image.
- `pixi-union-build`: Union's remote builder builds both images (it lowers the pixi layer to primitive layers) and a task runs in each.

### How to get to it (user POV)

Any task or workflow run, from a notebook or SDK code. Nothing changes for the user; the image recipe does.

### Driving it

Preconditions: docker; for the devbox, the devbox recipe in ticket `devbox-postgres-index`; for Union, `.flyte/union.yaml` and `STARGAZER_API_KEY_SECRET=UNION_API_KEY`.

- **Tasks tier.** `uv run --all-extras python cli/docker_task_tests.py` exits `0` (`pixi-tasks-tier`).
- **Tool versions.** `docker run --rm --platform linux/amd64 <gatk image> sh -c 'gatk --version; samtools --version | head -1; bwa 2>&1 | grep Version; bwa-mem2 version'` prints the versions in pixi.lock's `gatk` environment (`pixi-tool-versions`). The image name is the tasks tier's `image:` line.
- **Devbox germline.** `uv run --all-extras pytest -m devbox -rP tests/devbox/test_germline.py` passes both tests (`pixi-devbox-germline`).
- **Union.** From the repo root, with no `FLYTE_IMAGE_REGISTRY` exported, put the probe below in its own directory with a copy of `.dockerignore` (Flyte reads it from `root_dir`; without it the image hash and context change), then `uv run --all-extras python <dir>/pixi_probe.py $PWD/.flyte/union.yaml`. Both remote builds finish and both runs succeed, printing the locked tool versions and scanpy (`pixi-union-build`). Check `get run --in-phase running` is empty after.

```python
"""Probe the pixi-built task images on Union: tools, Python, stargazer."""

import subprocess
import sys
from pathlib import Path

import flyte

from stargazer.config import gatk_env, scrna_env

gatk_probe_env = flyte.TaskEnvironment(name="pixi_probe_gatk", image=gatk_env.image, resources=flyte.Resources(cpu=1, memory="2Gi"))
scrna_probe_env = flyte.TaskEnvironment(name="pixi_probe_scrna", image=scrna_env.image, resources=flyte.Resources(cpu=1, memory="2Gi"))


def _sh(cmd: str) -> str:
    r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, check=False)
    return f"$ {cmd}\n{r.stdout}{r.stderr}".strip()


@gatk_probe_env.task
async def probe_gatk() -> str:
    import stargazer

    return "\n".join([sys.executable, sys.version, stargazer.__file__, f"flyte {flyte.__version__}",
        _sh("gatk --version 2>&1 | grep -i jar"), _sh("samtools --version | head -1"),
        _sh("bwa 2>&1 | grep Version"), _sh("bwa-mem2 version 2>&1 | tail -1"), _sh("java -version 2>&1 | head -1")])


@scrna_probe_env.task
async def probe_scrna() -> str:
    import scanpy
    import stargazer

    return "\n".join([sys.executable, stargazer.__file__, f"scanpy {scanpy.__version__}", f"flyte {flyte.__version__}"])


if __name__ == "__main__":
    flyte.init_from_config(sys.argv[1], root_dir=Path(__file__).parent)
    for task in (probe_gatk, probe_scrna):
        run = flyte.run(task)
        print(run.url, flush=True)
        run.wait()
        print(run.outputs(), flush=True)
```

### Gotchas

- Without a `python` pin, pixi takes the newest conda-forge Python (3.15) over `requires-python = ">=3.14"`.
- bioconda's bwa-mem2 2.3 binary reports its version as `2.2.1`.
- Union's remote builder lowers the pixi layer to primitive layers, so its image hash differs from a local build of the same recipe.
- pixi.lock and uv.lock are separate resolutions, so they drift by lock date; the Flyte SDK must match between submitter and pod.

Related: [[board]], [[warm-uv-cache]], [[local-notebook-images]], [[layered-notebook-image-cache]], [[marimo-sandbox]], [[flyte-images]].
