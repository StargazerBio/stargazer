# Contributing

Stargazer has multiple contributor shapes — researchers writing notebooks, agent users driving the MCP server, code authors adding tasks, image maintainers publishing releases. Notebook authoring and the first step of task promotion both happen in the hosted notebook (see [Notebooks → Promotion](../architecture/notebook.md#promotion)); this guide covers working on the source itself — the SDK, the notebook runtime, and the images — natively against the repo.

## Setup

```bash
git clone https://github.com/StargazerBio/stargazer.git
cd stargazer
uv sync --all-extras
uv run pre-commit install
```

You now have:

- The stargazer package installed in editable mode in a project venv
- All Python deps from the lockfile, including every optional extra (scRNA, notebook, MCP, docs), plus the `dev` group (pytest, ruff, pre-commit)
- A pre-commit hook that lints, checks docstrings, builds the docs and runs the unit tests on every commit

The bioinformatics tools (gatk, bwa, bwa-mem2, samtools) aren't needed: their tests run in the task image (see [Running Tests](#running-tests)). Running those tasks locally, outside the tests, needs them on your PATH, from bioconda for instance.

## Running on the Devbox

Use `flyte start devbox` to run a local Flyte cluster, much closer to production than a local run. See the [official devbox docs](https://www.union.ai/docs/v2/flyte/user-guide/run-modes/running-devbox/). After every fresh devbox, apply the cluster-side fixes in the infrastructure repository's `devbox/setup.sh`, which also starts the Postgres server that holds the devbox's asset index. Stargazer's pods are x86_64, so on Apple silicon they run emulated (keep Docker Desktop's Rosetta setting on). Then point image builds at the devbox's registry:

```bash
export FLYTE_IMAGE_REGISTRY=localhost:30000
export FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false  # Apple silicon only
```

To have submitted runs store their assets on the devbox, also export `STARGAZER_STORE_ROOT`, `STARGAZER_INDEX_URL` and `STARGAZER_OWNER` (`setup.sh` prints the values) and keep its storage port-forward open. The devbox tests (`pytest -m devbox`) check that whole path.

## Running Tests

Each top-level directory under `tests/` belongs to one tier, and each tier has a pytest marker. The unit tier runs on every commit through pre-commit; run the others when your change reaches them.

```bash
uv run --all-extras pytest                            # unit: this venv
uv run --all-extras python cli/docker_task_tests.py   # tasks: in each task's image
uv run --all-extras pytest -m devbox                  # devbox: the local devbox
uv run --all-extras pytest -m pinata                  # the real Pinata API
uv run --all-extras pytest -m postgres                # the index on Postgres, in Docker
uv run --all-extras pytest -m dsql                    # the index on the real DSQL cluster
```

- **Unit** (`tests/assets`, `notebooks`, `unit`, `utils`) is the cheap tests that need only Python. Each test gets its own empty store, index and cache and no `PINATA_JWT`.
- **Tasks** (`tests/tasks`) runs each task's tests in the image the task runs in, so the GATK and alignment tools never need to be on your machine. Run it when you add or change a task. Pass paths or `-k` for a subset.
- **Devbox** (`tests/devbox`) is anything that needs a cluster. The devbox must be up with its setup applied and `FLYTE_IMAGE_REGISTRY` exported.
- **Pinata** (`tests/pinata`) calls the real Pinata API with the key in `tests/.secrets/pinata_jwt`.
- **Postgres** (`tests/postgres`) runs the index tests against a Postgres container it starts itself (needs Docker). Run it when you change the index.
- **DSQL** (`tests/dsql`) runs them against the hosted Aurora DSQL cluster, as its admin (needs `STARGAZER_DSQL_CLUSTER_ARN`).

Outside its tier a test is deselected, never skipped, and inside it a missing tool or service fails the run. A new directory under `tests/` needs a tier in `TIERS` in `tests/conftest.py`. The full testing conventions are in [the `write-tests` skill](https://github.com/StargazerBio/stargazer/blob/main/.claude/skills/write-tests/SKILL.md).

## Code Style

```bash
uv run ruff check --fix . && uv run ruff format .
```

Pre-commit runs `ruff` (lint and format) and `docstr-coverage` (a docstring on every module, class and function in `src/`), regenerates the catalog and API reference, builds the docs, checks the MCP server imports, and runs the unit tests.

Ruff is pinned twice — `rev:` in `.pre-commit-config.yaml` and the `ruff` entry in `pyproject.toml`'s dev group. **Bump both together**, or the commit hook and `uv run ruff` will enforce different rules. Deliberate rule exceptions live in `[tool.ruff.lint]` in `pyproject.toml`, each with the reason.

### Import Layers

Ruff also enforces the [architecture's layers](../architecture/overview.md): a module imports from its own layer or the ones below it, never above. The rules are in `src/stargazer/ruff.toml`. To draw the import graph into the gitignored `diagrams/`, run `cli/diagrams.sh` (see `cli/README.md`).

## Submitting Changes

Every change goes through a pull request — nothing is committed directly to `main`.

1. Make a worktree on a branch cut from an up-to-date `main`, named after the change in short kebab-case. Worktrees live under `.claude/worktrees/` (gitignored), and your main checkout stays on `main`:

    ```bash
    git fetch origin
    git worktree add --no-track .claude/worktrees/scrna-oom -b fix/scrna-oom origin/main
    ```

    The worktree starts without your Flyte configs and test secrets; link `.flyte/{config,union}.yaml` and `tests/.secrets` from the main checkout as the change needs them.

2. Commit as you go, one change per worktree.
3. When tests pass and the change works on its real surface, push and open a PR with `gh pr create --base main`. Say what changed and why, how you verified it, and anything deferred.
4. A maintainer reviews and merges. Address feedback with further commits on the same branch, then remove the worktree (`git worktree remove`) and `git pull` in your main checkout.

## Building Images

See [Configuration → Container Images](../architecture/configuration.md#container-images) for what each image is.

**Flyte task images (`stargazer-scrna`, `stargazer-gatk`)** build themselves, tagged by a hash of their recipe and the project's source, the first time a run or the tasks test tier needs them. `image.builder` in the Flyte config picks `local` (needs Docker) or `remote` (Union only).

**The notebook image (`stargazer`)** builds from `runtime/Dockerfile`, from the repository root, when you change it or want the current source in it:

```bash
docker build -f runtime/Dockerfile -t ghcr.io/stargazerbio/stargazer:latest .
```

Releases publish it; the tag above lets `docker run` resolve your local build by the published name.

## Releasing

A release is named by its date. Set `version` in `pyproject.toml` to today's date (`2026.11.27`, or `2026.11.27.1` for a second release that day) in a PR. Once it's merged, tag `main` with the same version and push the tag:

```bash
git tag v2026.11.27 origin/main
git push origin v2026.11.27
```

The **Release** workflow (`.github/workflows/release.yml`) checks the tag names the version, then publishes the package to PyPI as `stargazer-bio` and the image to `ghcr.io/stargazerbio/stargazer` under the tag and `latest`. The hosted dashboard picks a release up when its pin moves to it.
