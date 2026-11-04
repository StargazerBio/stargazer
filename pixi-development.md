---
title: pixi-development
status: doing
priority: normal
created: 2026-11-03
---

A task's dependencies belong to the environment that runs it, not to the package that defines it, and each environment declares them in a PEP 723 header in its own module, the way a notebook does. The SDK's `pyproject.toml` keeps only the core dependencies, and development moves from uv to pixi, so `uv.lock` goes. The third stage of [[pixi-dependencies]].

## Why

As the SDK grows its off-the-shelf tasks, one manifest would carry every domain's packages: a list that only grows, solved as one, so two domains with conflicting pins block each other (uv resolves every extra of a project together in one `uv.lock`). The `bio` extra is the first case: it's the scRNA tasks' packages, not anything general. Gating them in notebooks is wrong too: a notebook that submits a scRNA task never needs scanpy.

What decides where a dependency lives:

- **Submitting a task needs only the core.** The scRNA tasks import scanpy inside their bodies, so importing `stargazer.tasks`, `stargazer.workflows` and the MCP server loads neither scanpy nor anndata (measured 2026-11-04). AGENTS.md no longer asks for imports at the top of a file; a domain's packages import inside the task body.
- **Running a task needs its environment**, which its image installs. Each environment is solved on its own, so a new domain's pins can't break another's.
- **The environment is the unit**, not the task file: one header per `TaskEnvironment`, shared by its domain's tasks. A task file per image would mean dozens of builds and nothing shared.

## Design

**One module per environment, with its header.** Each domain's `TaskEnvironment` moves out of `config.py` into an `env.py` in its domain package, whose PEP 723 header lists the environment's packages: conda-forge and bioconda under `[tool.pixi.dependencies]`, PyPI under `dependencies`, channels and `platforms = ["linux-64"]` under `[tool.pixi.workspace]`. `pixi lock --script env.py` writes `env.py.pixi.lock` beside it. Its image is `flyte.Image.from_pixi_script(Path(__file__), name=..., platform=IMAGE_PLATFORM)`, which renders the header as a pixi project and installs it with `--locked` when the lock is there (read in Flyte 2.12.4's `_image.py` and `_internal/imagebuild/utils.py`).

```
src/stargazer/tasks/scrna/
    env.py              # header + scrna_env
    env.py.pixi.lock
    normalize.py        # from stargazer.tasks.scrna.env import scrna_env
```

```python
# /// script
# requires-python = ">=3.14"
# dependencies = ["stargazer-bio", "scanpy>=1.12", "anndata>=0.12.10", "scikit-image>=0.26", "igraph>=1.0", "pooch>=1.9"]
# [tool.pixi.workspace]
# channels = ["conda-forge", "bioconda"]
# platforms = ["linux-64"]
# [tool.pixi.dependencies]
# python = "3.14.*"
# ///
scrna_env = flyte.TaskEnvironment(
    name="scrna",
    image=flyte.Image.from_pixi_script(Path(__file__), name="stargazer-scrna", platform=IMAGE_PLATFORM)
    .with_source_folder(PROJECT_ROOT, "/opt/stargazer")
    .with_commands(["uv pip install /opt/stargazer"]),
    ...
)
```

The gatk environment's header lists gatk4, samtools, bwa and bwa-mem2 under `[tool.pixi.dependencies]`.

**Every header lists `stargazer-bio`, as notebook headers do.** The core dependencies are then locked in each environment's lock without being repeated. A release's image is the header alone, on the released SDK (ticket [[release-task-images]]). From a checkout, the source layer installs the checkout over it; without `--no-deps`, uv adds only core dependencies new since the release. This keeps [[pixi-layer-cache]]'s split: the environment layer is cached until the header or its lock changes. `from_pixi_script` builds on a debian base with `install_flyte=False`, which would also drop the base's unused `/opt/venv` (read in the code, not measured).

**`pyproject.toml` holds the core and development.** `[project.dependencies]` is what defining and submitting a task needs: flyte, the asset types, storage, the index. No domain extras: `bio` becomes the scrna header. `mcp` stays an extra, since it's what the `stargazer` command runs. `[tool.pixi]` declares only the dev environment: the `dev` group, the SDK editable (`stargazer-bio = { path = ".", editable = true }` in the dev feature, so no image environment is ever editable), and `osx-arm64` beside `linux-64` so the environment builds on a contributor's Mac.

**Development under pixi.** `pixi.lock` replaces `uv.lock`. The test tiers, the five `uv run` pre-commit hooks, `cli/docker_task_tests.py` (whose test packages are pinned from `uv.lock` today) and `.github/workflows/release.yml` (`uv build` → a build inside the pixi environment; setuptools still builds the wheel; `prefix-dev/setup-pixi` in CI) run under pixi. The ruff pin keeps matching `.pre-commit-config.yaml`'s rev.

**Tests.** A domain's tests run in its image, as the tasks tier does now. Collection does too, or the domain's test modules stop importing its packages at module level: today `cli/docker_task_tests.py` collects in the dev venv, and the unit tier's collection fails without scanpy.

## Open questions

- Union's remote builder with a script layer. Flyte lowers it to a generated pixi project, the path PR 127 proved for projects, but it's unbuilt.
- `pixi lock --script` with conda dependencies at pixi 0.72.2, Flyte's pinned version.
- "On this machine" for a notebook: run the task in its image with docker rather than in the kernel, so notebooks never install a domain's packages. Whether Flyte 2 can run a task in its container locally; if not, `stargazer.notebooks.ui.dispatch` does it, as `cli/docker_task_tests.py` does. On Apple silicon the images run emulated.
- What the dev environment carries for the domains: every header's packages (so domain tests collect locally) or none (collection in the images). Bioconda's `osx-arm64` coverage for tools added later; GenomicsDB stays x86_64-only, so joint calling never runs natively on a Mac.

## Plan

- [ ] Spike: the scrna environment as `tasks/scrna/env.py`, built locally and by Union's builder, with the tasks tier. Settles the first two open questions.
- [ ] Every environment in its domain's `env.py`; `config.py` keeps the shared settings (`IMAGE_PLATFORM`, `STARGAZER_ENV_VARS`, `STARGAZER_SECRETS`). `pyproject.toml` loses `[tool.pixi]`'s image environments and the `bio` extra.
- [ ] Development under pixi: the dev environment, the tiers, pre-commit, release, `uv.lock` removed.
- [ ] AGENTS.md (where environments live, how to add a tool), the `tasks-and-workflows` and `write-tests` skills, Contributing, Configuration → Container Images, the wiki's `flyte-images` and `gatk` pages.

Related: [[board]], [[pixi-dependencies]], [[pixi-layer-cache]], [[drop-notebook-extra]], [[release-task-images]], [[pixi-notebook-sandbox]], [[flyte-images]].
