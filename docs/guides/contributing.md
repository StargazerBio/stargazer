# Contributing

Stargazer has multiple contributor shapes — researchers writing notebooks, agent users driving the MCP server, code authors adding tasks, image maintainers publishing releases. Notebook authoring, snapshot freezing, and the first step of task promotion all happen in the hosted notebook (see [Notebooks → User Archetypes](../architecture/notebook.md#user-archetypes)); this guide covers working on the source itself — the SDK, the app tier, and the images — natively against the repo.

## Setup

```bash
git clone https://github.com/StargazerBio/stargazer.git
cd stargazer
uv sync --all-extras
uv run pre-commit install
```

You now have:

- The stargazer package installed in editable mode in a project venv
- All Python deps from the lockfile, including every optional extra (scRNA, notebook, MCP, app tier, docs), plus the `dev` group (pytest, ruff, pre-commit)
- A pre-commit hook that lints, checks docstrings, builds the docs and runs the unit tests on every commit

The bioinformatics tools (gatk, bwa, bwa-mem2, samtools) aren't needed: their tests run in the task image (see [Running Tests](#running-tests)). Running those tasks locally, outside the tests, needs them on your PATH, from bioconda for instance.

## Running on the Devbox

Use `flyte start devbox` to spin up a local Flyte cluster for development. See the [official devbox docs](https://www.union.ai/docs/v2/flyte/user-guide/run-modes/running-devbox/) for setup instructions.

Stargazer's images are built for x86_64 only, like the machines they run on in production. On Apple silicon the devbox itself runs natively and Stargazer's pods run under emulation, so they're slower than on Union. Docker Desktop runs them through Rosetta, so keep its Rosetta setting enabled.

This environment is much closer to production and lets you actually test your task and app environments. After every fresh devbox, apply the cluster-side fixes, then deploy a dashboard to hold the asset index:

```bash
cli/devbox-setup.sh                      # prints the one-time DNS steps for your machine too
uv run --all-extras python cli/devbox_dashboard.py
```

The dashboard opens at `http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081` as a stand-in user, `devbox-user`. To have runs you submit store their assets there, export these first and keep the storage port-forward open while submitting:

```bash
export STARGAZER_STORE_ROOT=s3://flyte-data/stargazer
export STARGAZER_INDEX_URL=http://dashboard-flytesnacks-development.flyte.svc.cluster.local
export STARGAZER_OWNER=devbox-user
kubectl port-forward -n flyte svc/rustfs-svc 9000:9000
```

The devbox tests (`uv run --all-extras pytest -m devbox`, see [Running Tests](#running-tests)) check that whole path: they deploy the dashboard, store and find assets across pods, and run the germline workflow.

## Running Tests

Each top-level directory under `tests/` belongs to one tier, and each tier has a pytest marker. The unit tier runs on every commit through pre-commit; run the others when your change reaches them.

```bash
uv run --all-extras pytest                            # unit: this venv
uv run --all-extras python cli/docker_task_tests.py   # tasks: in each task's image
uv run --all-extras pytest -m devbox                  # devbox: the local devbox
uv run --all-extras pytest -m pinata                  # the real Pinata API
```

- **Unit** (`tests/assets`, `notebooks`, `unit`, `utils`) is the cheap tests that run on Python alone. Every test gets its own empty store, index and cache under its temp directory, so nothing touches `~/.stargazer`, and runs with no `PINATA_JWT`. Tests that query the fixture files use a store seeded once per session (`tests/fixtures/seed.py`).
- **Tasks** (`tests/tasks`) runs each task's tests in the image the task runs in, so the GATK and alignment tools never need to be on your machine. Run it when you add or change a task. The runner builds those images as a pod gets them, x86_64 like Union (emulated on Apple silicon), and runs the tests in them. A source change rebuilds the images first. Pass paths or `-k` to run a subset, such as `tests/tasks/gatk/test_sort_sam.py`.
- **Devbox** (`tests/devbox`) is anything that needs a cluster: deploying the dashboard, workflows across pods, the devbox's store and index. It deploys the dashboard itself; the devbox has to be up with `cli/devbox-setup.sh` applied. Add `-rP` to see each run's URL.
- **Pinata** (`tests/pinata`) calls the real Pinata API with the key in `tests/.secrets/pinata_jwt`, and fails without it.

Outside its tier a test is deselected, never skipped, and inside it a missing tool or service fails the run. A new directory under `tests/` needs a tier in `TIERS` in `tests/conftest.py`. The full testing conventions are in [`.opencode/agent/test.md`](https://github.com/StargazerBio/stargazer/blob/main/.opencode/agent/test.md).

## Code Style

```bash
uv run ruff check --fix . && uv run ruff format .
```

Pre-commit runs `ruff` (lint and format) and `docstr-coverage` (a docstring on every module, class and function in `src/`), regenerates the catalog and API reference, builds the docs, checks the MCP server imports, and runs the unit tests.

Ruff is pinned twice — `rev:` in `.pre-commit-config.yaml` and the `ruff` entry in `pyproject.toml`'s dev group — because pre-commit runs hooks in its own isolated environment rather than your project venv. **Bump both together**, or `uv run ruff check` and the commit hook will enforce different rule sets. Rule exceptions live in `[tool.ruff.lint]` in `pyproject.toml`, each annotated with the reason; if a rule is fighting a deliberate pattern (a blind `except` used for graceful degradation, a bare expression that is how a marimo cell renders), add it there rather than contorting the code.

## Submitting Changes

Every change goes through a pull request — nothing is committed directly to `main`.

1. Cut a branch from an up-to-date `main`, named after the change in short kebab-case:

    ```bash
    git switch main && git pull
    git switch -c fix/scrna-oom
    ```

2. Commit as you go. Keep the branch to one change; an unrelated fix gets its own branch.
3. When tests pass and the change works on its real surface, push and open a PR against `main`:

    ```bash
    git push -u origin fix/scrna-oom
    gh pr create --base main
    ```

    Say what changed and why, how you verified it, and anything you deferred.

4. A maintainer reviews the PR and merges it. Address review feedback with further commits on the same branch.

## Building Images

See [Configuration → Container Images](../architecture/configuration.md#container-images) for the split between Flyte task images and human-runnable images. `uv add` covers Python deps via the lockfile, and contributors pulling your branch pick the change up on their next `uv sync`.

**Flyte task images (`stargazer-scrna`, `stargazer-gatk`)** build themselves. Each is tagged by a hash of its recipe and the project's source, so a change to either builds a new one the first time something needs it: a run on the devbox or Union, or the tasks test tier, which builds into your local docker without pushing anywhere. `image.builder` in the Flyte config picks `local` (needs a working Docker daemon) or `remote` (Union only, builds on the cluster). Runs push to `STARGAZER_REGISTRY` — the devbox's own registry by default when targeting the devbox.

**Human-runnable images (`stargazer-note`, `stargazer-chat`)** build from the `Dockerfile` when you change it or want the current source in them:

```bash
docker build --target note -t ghcr.io/stargazerbio/stargazer-note:latest .
docker build --target chat -t ghcr.io/stargazerbio/stargazer-chat:latest .
```

Tag both with the published `ghcr.io/stargazerbio/...` URL even though you're not pushing — `docker run` resolves them from the local cache by that name. Nothing publishes them automatically. A maintainer publishes both platforms with buildx, logged in to `ghcr.io` with a token that has `write:packages`:

```bash
docker buildx build --platform linux/amd64,linux/arm64 --target note -t ghcr.io/stargazerbio/stargazer-note:latest --push .
docker buildx build --platform linux/amd64,linux/arm64 --target chat -t ghcr.io/stargazerbio/stargazer-chat:latest --push .
```

The hosted notebook pods use a different image, `notebook-app`, built by the onboarding command (`stargazer-users`) — see [App → Images](../architecture/app.md#images). The shared `base` stage (bioconda CLIs + uv + project venv) is reused between targets, so the second `docker build` is mostly cache hits.
