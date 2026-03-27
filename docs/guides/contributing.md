# Contributing

## Setup

Clone the repo and build the `chat` image:

```bash
git clone <repo-url>
cd stargazer
docker build --target chat -t stargazer:chat .
```

Mount your local checkout into the container so edits are reflected immediately:

```bash
docker run -it -v $(pwd):/stargazer stargazer:chat
```

The entrypoint runs `uv sync --group dev` then drops you into a shell with Claude Code, OpenCode, and standard dev tooling. The package is installed in editable mode, so changes to `src/` take effect without reinstalling.

## Running Tests

```bash
pytest tests/
```

Tests run with no `PINATA_JWT`. The test harness points `LocalStorageClient` at a temporary directory and never mutates client internals. Tests that need Pinata behavior mock the API or skip.

Run only unit or integration tests:

```bash
pytest tests/unit/
pytest tests/integration/
```

## Code Style

Run `ruff` before committing:

```bash
ruff --fix .
```

The pre-commit hooks enforce `ruff` formatting and `docstr-coverage` (100% module-level docstrings required).
