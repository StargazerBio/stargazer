---
title: pixi-development
status: review
priority: normal
created: 2026-11-03
pr: 130
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

- ~~Union's remote builder with a script layer.~~ It builds them (measured 2026-11-04): scrna 1:25 and gatk 1:38 cold, 0:08 to 0:09 for a source-only rebuild, and a probe task succeeded on each.
- ~~`pixi lock --script` with conda dependencies at pixi 0.72.2.~~ 0.72.2 has no `--script` at all. A lock from 0.84's `pixi lock --script` is refused by 0.72.2's `--locked` ("declares virtual packages [] but the lock-file was solved with [__unix=0]"; 0.72.2 writes `__unix=0=0`), and 0.72.2's own `lock --check` exits 0 on a lock it rewrites. So `cli/lock_envs.py` renders the header with Flyte's `render_pixi_manifest`, locks it with `ghcr.io/prefix-dev/pixi:<Flyte's PIXI_VERSION>` in docker, and checks by comparing a relocked copy. The same mismatch means no image can install from the dev `pixi.lock` (written by a local pixi 0.84): `with_pixi_project(pyproject.toml)` fails `--locked`.
- "On this machine" for a notebook: run the task in its image with docker rather than in the kernel, so notebooks never install a domain's packages. Whether Flyte 2 can run a task in its container locally; if not, `stargazer.notebooks.ui.dispatch` does it, as `cli/docker_task_tests.py` does. On Apple silicon the images run emulated.
- ~~What the dev environment carries for the domains.~~ None: the scRNA tests import scanpy inside their bodies, so collection needs no domain's packages, and the tasks tier still collects in the dev environment. Bioconda's `osx-arm64` coverage for tools added later; GenomicsDB stays x86_64-only, so joint calling never runs natively on a Mac.

## Plan

- [x] Spike: the scrna environment as `tasks/scrna/env.py`, built locally and by Union's builder, with the tasks tier. Settles the first two open questions.
- [x] Every environment in its domain's `env.py`; `config.py` keeps the shared settings (`IMAGE_PLATFORM`, `STARGAZER_ENV_VARS`, `STARGAZER_SECRETS`). `pyproject.toml` loses `[tool.pixi]`'s image environments and the `bio` extra.
- [x] Development under pixi: the dev environment, the tiers, pre-commit, release, `uv.lock` removed.
- [x] AGENTS.md (where environments live, how to add a tool), the `tasks-and-workflows` and `write-tests` skills, Contributing, Configuration → Container Images, the wiki's `flyte-images` and `gatk` pages.
- [x] Found in review: the template's and the Tasks tutorial's own task images (`with_uv_project`, which Union's builder skips without a uv.lock) build from a core environment, `src/stargazer/env.py` (the SDK alone), with `task_image()`. The notebook image's MCP venv installs under pins read from `pixi.lock`.

## Verification recipe: task environments from their headers

Each domain's environment is the PEP 723 header of its `env.py`, locked beside it; its image builds from that header with `from_pixi_script` and the checkout's source on top, locally and on Union's remote builder, and every task runs in it as before. Development runs under pixi with no domain's packages.

### Sub-features

- `env-tasks-tier`: every task test passes in its domain's image.
- `env-devbox-germline`: the germline workflow runs on the devbox on the gatk image.
- `env-union-build`: Union builds the gatk, scrna and tutorial images and a probe task runs on each, stargazer from site-packages, the locked tools and flyte.
- `env-locks`: `cli/lock_envs.py --check` fails on a header changed without relocking and passes otherwise.
- `dev-env`: the unit tier passes under `pixi run pytest` on a Mac, with no scanpy installed.
- `notebook-image`: the notebook image builds, and its MCP venv imports the server on the pinned flyte.

### How to get to it (user POV)

Any task or workflow run, from a notebook or SDK code; for a contributor, `pixi run` in a fresh checkout.

### Driving it

Preconditions: pixi, docker, the devbox (ticket `devbox-postgres-index`), `.flyte/union.yaml` linked, `STARGAZER_API_KEY_SECRET=UNION_API_KEY` and no `FLYTE_IMAGE_REGISTRY` for Union.

- **Tasks tier.** `pixi run python cli/docker_task_tests.py` exits 0 (`env-tasks-tier`).
- **Devbox.** `FLYTE_IMAGE_REGISTRY=localhost:30000 FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false pixi run pytest -m devbox -rP tests/devbox/test_germline.py` passes both (`env-devbox-germline`).
- **Union.** The probe in [[pixi-dependencies]]'s recipe, with the environments imported from `stargazer.tasks.gatk.env` and `stargazer.tasks.scrna.env`, and each task defined at module level (a pod imports the module, so nothing may depend on `sys.argv`); a third probe on `stargazer.notebooks.tutorials.tasks.tutorial_env.image` importing `aiohttp`, `marimo` and `stargazer`. Each prints `/opt/pixi-project/.pixi/envs/default/...` paths and flyte matching `pixi.lock` (`env-union-build`).
- **Locks.** Add a package not in the lock to a header's `dependencies`, `pixi run python cli/lock_envs.py --check` exits 1; restore it, exit 0 (`env-locks`).
- **Dev.** `pixi run pytest` passes; `pixi run python -c "import scanpy"` fails (`dev-env`).
- **Notebook image.** `docker build -f runtime/Dockerfile -t sg-test .`, then `docker run --rm --entrypoint sh sg-test -c '/opt/mcp/bin/python -c "from stargazer.server import mcp; import flyte; print(flyte.__version__)"'` (`notebook-image`).

### Gotchas

- Adding a package the lock already holds (a transitive dependency) leaves the lock unchanged, and `--check` rightly passes: test with a package that isn't in it.
- The image's pixi environment is root's and the pod runs as `flyte`, so nothing installs into it at runtime; the tasks tier installs pytest into a `--target` directory.
- Deleting `.venv` or `.pixi` under a running submitter kills it after its build.

## Evidence (2026-11-04)

- Tasks tier: 20 gatk/general and 15 scrna passed (3:04, images built locally, emulated).
- Devbox germline: 2 passed in 2:28.
- Union: scrna probe `umcssd9dqwht86m4nbrn` (scanpy 1.12.5), gatk probe `uhnd7bwg97m7hhrmpjcn` (gatk 4.6.2.0, samtools 1.25, bwa 0.7.19-r1273, bwa-mem2 reporting 2.2.1, Java 17), tutorial probe `u5gk84dzqwc974d4ff7m` (aiohttp 3.14.5, marimo 0.23.16), all on flyte 2.12.4 with stargazer in site-packages and no `/opt/venv`.
- Unit tier under pixi on osx-arm64: passed, scanpy absent.
- Notebook image: built; `/opt/mcp` runs flyte 2.12.4 and mcp 2.3.0.

Related: [[board]], [[pixi-dependencies]], [[pixi-layer-cache]], [[drop-notebook-extra]], [[release-task-images]], [[pixi-notebook-sandbox]], [[flyte-images]].
