# Contributing

Stargazer has multiple contributor shapes — researchers writing notebooks, agent users driving the MCP server, code authors adding tasks, image maintainers publishing releases. The end-user images (`note`, `chat`) are products, not dev environments. Source contributors work natively against the repo.

## Setup

```bash
git clone <repo-url>
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

Image rebuilds are only needed when you change `config.py` (a system tool, a new env, etc.). Routine code work doesn't need this — `uv add` covers Python deps via the lockfile, and contributors pulling your branch pick the change up automatically on their next `uv sync`.

When you do need to rebuild, do it natively from your host shell — the chat container is not in the loop.

**Local Docker** (default — `image.builder: local` in `.flyte/config.yaml`):

```bash
docker login <registry>
stargazer-build-images
```

**Remote (Union ImageBuilder):** set `image.builder: remote` in `.flyte/config.yaml`, then `stargazer-build-images`. No local Docker needed; only available against a Union backend.

> **Migration note:** the legacy `Dockerfile` is still present until the new flow is verified end-to-end. While it lives, `docker build --target chat -t stargazer:chat .` is a working fallback. Once signed off, the `Dockerfile` will be removed.
