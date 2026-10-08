# Contributing

Stargazer has multiple contributor shapes — researchers writing notebooks, agent users driving the MCP server, code authors adding tasks, image maintainers publishing releases. Notebook authoring, snapshot freezing, and the first step of task promotion all happen in the hosted notebook (see [Notebooks → User Archetypes](../architecture/notebook.md#user-archetypes)); this guide covers working on the source itself — the SDK, the app tier, and the images — natively against the repo.

## Setup

```bash
git clone https://github.com/StargazerBio/stargazer.git
cd stargazer
mamba install -y -c bioconda -c conda-forge bwa bwa-mem2 samtools gatk4
uv sync --all-extras
```

You now have:

- The stargazer package installed in editable mode in a project venv
- All Python deps from the lockfile, including every optional extra (scRNA, notebook, MCP, app tier, docs), plus the `dev` group (pytest, ruff, pre-commit)
- Bioconda CLIs on PATH (only needed if you'll run `gatk_env` / `general` tasks locally)

If you don't have mamba/conda on your host, install [miniforge](https://github.com/conda-forge/miniforge) first. The bioconda step is skippable if you only intend to work on `scrna` tasks (pure Python) or the MCP server.

## Running on the Devbox

Use `flyte start devbox` to spin up a local Flyte cluster for development. See the [official devbox docs](https://www.union.ai/docs/v2/flyte/user-guide/run-modes/running-devbox/) for setup instructions.

This environment is much closer to production and lets you actually test your task and app environments.

## Running Tests

```bash
pytest tests/
```

Tests run with no `PINATA_JWT`. Every test gets its own empty store, index and cache under its temp directory, so nothing touches `~/.stargazer`; tests that query the fixture files use a store seeded once per session (`tests/fixtures/seed.py`). Tests marked `pinata` call the real Pinata API with the key in `tests/.secrets/pinata_jwt`. They don't run by default; `uv run pytest -m pinata` runs them, and they skip without the key.

```bash
pytest tests/unit/
pytest tests/integration/
```

## Code Style

```bash
ruff --fix .
```

Pre-commit enforces `ruff` formatting and `docstr-coverage` (100% module-level docstrings required).

Ruff is pinned twice — `rev:` in `.pre-commit-config.yaml` and the `ruff` entry in `pyproject.toml`'s dev group — because pre-commit runs hooks in its own isolated environment rather than your project venv. **Bump both together**, or `ruff --fix .` and the commit hook will enforce different rule sets. Rule exceptions live in `[tool.ruff.lint]` in `pyproject.toml`, each annotated with the reason; if a rule is fighting a deliberate pattern (a blind `except` used for graceful degradation, a bare expression that is how a marimo cell renders), add it there rather than contorting the code.

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

Image rebuilds are only needed when you change `config.py` (a Flyte task tool/env) or the `Dockerfile` (a system tool in the human-runnable note/chat images). Routine code work doesn't need this — `uv add` covers Python deps via the lockfile, and contributors pulling your branch pick the change up automatically on their next `uv sync`. See [Configuration → Container Images](../architecture/configuration.md#container-images) for the split between Flyte task images and human-runnable images.

All builds below stay local — nothing is pushed to a registry, so you don't need `docker login` or write access to `ghcr.io/stargazerbio`. CI will handle publishing on merge to main.

**Flyte task images (`stargazer-scrna`, `stargazer-gatk`):**

```bash
stargazer-build-images   # builds scrna and gatk into the local docker cache
```

`image.builder: local` in `.flyte/config.yaml` is the default (needs a working Docker daemon). The Flyte images have no `registry=` set in `config.py`, so the docker builder uses `--load` and the results land in `docker images` rather than being pushed. For Union backends you can flip to `image.builder: remote` and the build runs on the cluster instead.

**Human-runnable images (`stargazer-note`, `stargazer-chat`):**

```bash
docker build --target note -t ghcr.io/stargazerbio/stargazer-note:latest .
docker build --target chat -t ghcr.io/stargazerbio/stargazer-chat:latest .
```

Tag both with the published `ghcr.io/stargazerbio/...` URL even though you're not pushing — `docker run` resolves them from the local cache by that name. (The hosted notebook pods use a different image, `notebook-app`, built by the onboarding command (`stargazer-users`) — see [App → Images](../architecture/app.md#images).) The shared `base` stage (bioconda CLIs + uv + project venv) is reused between targets, so the second `docker build` is mostly cache hits.
