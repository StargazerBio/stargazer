# Contributing

Stargazer has multiple contributor shapes — researchers writing notebooks, agent users driving the MCP server, code authors adding tasks, image maintainers publishing releases. The end-user images (`note`, `chat`) are products, not dev environments. Source contributors work natively against the repo.

## Setup

```bash
git clone https://github.com/StargazerBio/stargazer.git
cd stargazer
mamba install -y -c bioconda -c conda-forge bwa bwa-mem2 samtools gatk4
uv sync --group dev
```

You now have:

- The stargazer package installed in editable mode in a project venv
- All Python deps from the lockfile, plus the `dev` group (pytest, ruff, pre-commit)
- Bioconda CLIs on PATH (only needed if you'll run `gatk_env` / `general` tasks locally)

If you don't have mamba/conda on your host, install [miniforge](https://github.com/conda-forge/miniforge) first. The bioconda step is skippable if you only intend to work on `scrna` tasks (pure Python) or the MCP server.

## Running Tests

```bash
pytest tests/
```

Tests run with no `PINATA_JWT`. The harness points `LocalStorageClient` at a temporary directory and never mutates client internals. Tests that need Pinata behavior mock the API or skip.

```bash
pytest tests/unit/
pytest tests/integration/
```

## Code Style

```bash
ruff --fix .
```

Pre-commit enforces `ruff` formatting and `docstr-coverage` (100% module-level docstrings required).

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

Tag both with the published `ghcr.io/stargazerbio/...` URL even though you're not pushing — that way `flyte.serve(note_env)` resolves the tag from your local cache (`note_env.image` references that URL), and `docker run` works for the same reason. The shared `base` stage (bioconda CLIs + uv + project venv) is reused between targets, so the second `docker build` is mostly cache hits.
