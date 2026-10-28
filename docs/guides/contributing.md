# Contributing

Stargazer has multiple contributor shapes — researchers writing notebooks, agent users driving the MCP server, code authors adding tasks, image maintainers publishing releases. Notebook authoring and the first step of task promotion both happen in the hosted notebook (see [Notebooks → User Archetypes](../architecture/notebook.md#user-archetypes)); this guide covers working on the source itself — the SDK, the notebook runtime, and the images — natively against the repo.

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

Use `flyte start devbox` to spin up a local Flyte cluster for development. See the [official devbox docs](https://www.union.ai/docs/v2/flyte/user-guide/run-modes/running-devbox/) for setup instructions.

Stargazer's images are built for x86_64 only, like the machines they run on in production. On Apple silicon the devbox itself runs natively and Stargazer's pods run under emulation, so they're slower than on Union. Docker Desktop runs them through Rosetta, so keep its Rosetta setting enabled.

This environment is much closer to production and lets you actually test your task environments. After every fresh devbox, apply the cluster-side fixes in the infrastructure repository's `devbox/setup.sh`, which also start the Postgres server that holds the devbox's asset index; a dashboard for the devbox deploys from there too. Then point your Flyte config at the devbox's registry, so the images your runs build go where the devbox pulls from. In `.flyte/config.yaml`:

```yaml
image:
  builder: local
  registry: localhost:30000
```

On Apple silicon also export `FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false` before a run builds an image ([Configuration → Container Images](../architecture/configuration.md#container-images) says why).

To have runs you submit store their assets on the devbox, export these first and keep the storage port-forward open while submitting:

```bash
export STARGAZER_STORE_ROOT=s3://flyte-data/stargazer
export STARGAZER_INDEX_URL=postgresql://stargazer:stargazer@postgres.stargazer.svc.cluster.local:5432/stargazer
export STARGAZER_OWNER=devbox-user
kubectl port-forward -n flyte svc/rustfs-svc 9000:9000
```

The devbox tests (`uv run --all-extras pytest -m devbox`, see [Running Tests](#running-tests)) check that whole path: they store and find assets across pods, check the index survives a restart of its Postgres server, and run the germline workflow.

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

- **Unit** (`tests/assets`, `notebooks`, `unit`, `utils`) is the cheap tests that run on Python alone. Every test gets its own empty store, index and cache under its temp directory, so nothing touches `~/.stargazer`, and runs with no `PINATA_JWT`. Tests that query the fixture files use a store seeded once per session (`tests/fixtures/seed.py`).
- **Tasks** (`tests/tasks`) runs each task's tests in the image the task runs in, so the GATK and alignment tools never need to be on your machine. Run it when you add or change a task. The runner builds those images as a pod gets them, x86_64 like Union (emulated on Apple silicon), and runs the tests in them. A source change rebuilds the images first. Pass paths or `-k` to run a subset, such as `tests/tasks/gatk/test_sort_sam.py`.
- **Devbox** (`tests/devbox`) is anything that needs a cluster: workflows across pods, the devbox's store and index. The devbox has to be up with its setup applied, and `.flyte/config.yaml` pointing at its registry. Add `-rP` to see each run's URL.
- **Pinata** (`tests/pinata`) calls the real Pinata API with the key in `tests/.secrets/pinata_jwt`, and fails without it.
- **Postgres** (`tests/postgres`) runs the index tests against a Postgres 16 container it starts and removes itself, so it needs Docker running. Run it when you change the index.
- **DSQL** (`tests/dsql`) runs the same index tests against the hosted index's Aurora DSQL cluster, as its admin, in a schema it makes and drops. It needs an admin's AWS session and the cluster's ARN in `STARGAZER_DSQL_CLUSTER_ARN`. Run it when you change the index's SQL or how it connects to DSQL.

Outside its tier a test is deselected, never skipped, and inside it a missing tool or service fails the run. A new directory under `tests/` needs a tier in `TIERS` in `tests/conftest.py`. The full testing conventions are in [the `write-tests` skill](https://github.com/StargazerBio/stargazer/blob/main/.claude/skills/write-tests/SKILL.md).

## Code Style

```bash
uv run ruff check --fix . && uv run ruff format .
```

Pre-commit runs `ruff` (lint and format) and `docstr-coverage` (a docstring on every module, class and function in `src/`), regenerates the catalog and API reference, builds the docs, checks the MCP server imports, and runs the unit tests.

Ruff is pinned twice — `rev:` in `.pre-commit-config.yaml` and the `ruff` entry in `pyproject.toml`'s dev group — because pre-commit runs hooks in its own isolated environment rather than your project venv. **Bump both together**, or `uv run ruff check` and the commit hook will enforce different rule sets. Rule exceptions live in `[tool.ruff.lint]` in `pyproject.toml`, each annotated with the reason; if a rule is fighting a deliberate pattern (a blind `except` used for graceful degradation, a bare expression that is how a marimo cell renders), add it there rather than contorting the code.

### Import Layers

Ruff also enforces the [architecture's layers](../architecture/overview.md): a module imports from its own layer or the ones below it, never above. Each layer's directory has a `ruff.toml` that bans the layers above it, and the rules are written out in `src/stargazer/ruff.toml`. A task that imports a workflow fails lint:

```
TID251 `stargazer.workflows` is banned: Workflows are above tasks (layers: src/stargazer/ruff.toml)
```

A nested `ruff.toml`'s ban list replaces its parent's rather than adding to it, so a new layer directory lists every ban that applies to it.

### Import Diagrams

To see how the modules depend on each other, draw the import graph. The script installs what it needs, Graphviz included, through uv:

```bash
cli/diagrams.sh                            # the SDK by package and by module
cli/diagrams.sh src/stargazer/server.py    # one module and everything it imports
```

The SVGs land in `diagrams/`, which is gitignored: draw them when you need them rather than committing them. Open them in a browser to zoom.

## Submitting Changes

Every change goes through a pull request — nothing is committed directly to `main`.

1. Make a worktree for the change, on a branch cut from an up-to-date `main` and named after the change in short kebab-case. Worktrees live under `.claude/worktrees/`, which is gitignored, and your main checkout stays on `main`:

    ```bash
    git fetch origin
    git worktree add --no-track .claude/worktrees/scrna-oom -b fix/scrna-oom origin/main
    cd .claude/worktrees/scrna-oom
    ```

    `uv run` gives the worktree its own venv, but it starts without your Flyte configs and test secrets. Link the ones the change needs from the main checkout: the Flyte configs for anything that runs on the devbox or Union, the Pinata key for the pinata tier:

    ```bash
    MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
    mkdir -p .flyte && ln -s "$MAIN"/.flyte/{config,union}.yaml .flyte/
    ln -s "$MAIN/tests/.secrets" tests/.secrets
    ```

2. Commit as you go. Keep the worktree to one change; an unrelated fix gets its own.
3. When tests pass and the change works on its real surface, push and open a PR against `main`:

    ```bash
    git push -u origin fix/scrna-oom
    gh pr create --base main
    ```

    Say what changed and why, how you verified it, and anything you deferred.

4. A maintainer reviews the PR and merges it. Address review feedback with further commits on the same branch. Once it's merged, remove the worktree with `git worktree remove .claude/worktrees/scrna-oom`, and `git pull` in your main checkout to keep its `main` current.

## Building Images

See [Configuration → Container Images](../architecture/configuration.md#container-images) for what each image is. `uv add` covers Python deps via the lockfile, and contributors pulling your branch pick the change up on their next `uv sync`.

**Flyte task images (`stargazer-scrna`, `stargazer-gatk`)** build themselves. Each is tagged by a hash of its recipe and the project's source, so a change to either builds a new one the first time something needs it: a run on the devbox or Union, or the tasks test tier, which builds into your local docker without pushing anywhere. `image.builder` in the Flyte config picks `local` (needs a working Docker daemon) or `remote` (Union only, builds on the cluster), and a local build pushes to the config's `image.registry`.

**The notebook image (`stargazer`)** builds from `runtime/Dockerfile`, from the repository root, when you change it or want the current source in it:

```bash
docker build -f runtime/Dockerfile -t ghcr.io/stargazerbio/stargazer:latest .
```

Tag it with the published `ghcr.io/stargazerbio/...` URL even though you're not pushing — `docker run` resolves it from the local cache by that name. Releases publish it.

## Releasing

A release is named by its date. Set `version` in `pyproject.toml` to today's date (`2026.11.27`, or `2026.11.27.1` for a second release that day) in a PR. Once it's merged, tag `main` with the same version and push the tag:

```bash
git tag v2026.11.27 origin/main
git push origin v2026.11.27
```

The **Release** workflow (`.github/workflows/release.yml`) checks the tag names the version, then publishes the package to PyPI as `stargazer-bio` and the image to `ghcr.io/stargazerbio/stargazer` under the tag and `latest`. The hosted dashboard picks a release up when its pin moves to it.
