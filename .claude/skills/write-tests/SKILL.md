---
name: write-tests
description: "Write Stargazer tests: the five test tiers and where each runs, per-test store isolation, the fixtures_db seeded store, task and workflow test templates, and generating test assets in a task's image. Use before implementing any change, and whenever adding, running or fixing tests."
---

# Write tests

Focused tests for Stargazer's tasks, workflows and the code around them, written before the implementation. This is the reference for the test tiers, isolation and fixtures.

## Core Principles

1. **Test Before Implementation**: Write tests first to validate behavior
2. **Small and Focused**: Each test should verify one specific behavior
3. **Use Real Tools**: Task tests run the real tool in the task's image; nothing is mocked
4. **Clear Assertions**: Make test failures informative
5. **Test Isolation**: Each test gets its own empty store; no test depends on another

## Project Testing Strategy

The Stargazer project follows this process:
1. **Write simple tests first** - before implementation
2. **Confirm each test fails for the expected reason** - missing behavior, not an import error or broken fixture. No pause for user review
3. **Implement tightly scoped functionality**
4. **Run tests until they pass**
5. **Small, meaningful commits on the change's branch** - the user reviews the pull request, tests and implementation together

Assert observable behavior against literal expected values. If a test would still pass when the code under test returns `None`, rewrite the assertion or delete it.

Don't restate configuration in a test. A version pin, a resource size or any other chosen value changes with the choice, so a test that hardcodes it only gets edited alongside it. Check what the value does on its real surface instead.

## Test Tiers

Every top-level directory under `tests/` belongs to exactly one tier, and its tests carry that tier's marker. The mapping is `TIERS` in `tests/conftest.py`; a new directory has to be added there, or the run stops with an error naming it. A bare `pytest` run is the unit tier (`addopts` in `pyproject.toml`); `-m` picks another.

| Tier | Marker | Directories | Where it runs | When | Command |
|------|--------|-------------|---------------|------|---------|
| Unit | `unit` | `assets/`, `notebooks/`, `unit/`, `utils/` | This venv | Every commit (pre-commit) | `uv run --all-extras pytest` |
| Tasks | `tasks` | `tasks/` | Each task's image, x86_64 | When you add or change a task | `uv run --all-extras python cli/docker_task_tests.py` |
| Devbox | `devbox` | `devbox/` | The local devbox | When a change reaches the cluster | `uv run --all-extras pytest -m devbox` |
| Pinata | `pinata` | `pinata/` | Against the real Pinata API | When the Pinata client changes | `uv run --all-extras pytest -m pinata` |
| Postgres | `postgres` | `postgres/` | Against a throwaway Postgres container (Docker) | When the index changes | `uv run --all-extras pytest -m postgres` |

- **Unit:** cheap tests that run on Python alone: the asset types, the app tier, storage and the index, the notebook smoke tests. `--all-extras` because the notebook smoke tests need the `notebook` extra and the app tests `landing`.
- **Tasks:** every test of a task, in the image that task runs in. `tests/tasks/<domain>` runs in the image of its domain's `TaskEnvironment` (`IMAGES` in `cli/docker_task_tests.py` maps each). So a task test checks what a pod gets, and no one installs the tools. The runner builds each image as a task pod gets it, with the project installed, and mounts only `tests/` and `pyproject.toml`, so a source change builds the images again before the tests run. x86_64 like Union, emulated on Apple silicon.
- **Devbox:** anything that needs a cluster: deploying the dashboard, running workflows across pods, the devbox's object store and its Postgres index. The session deploys the dashboard once for the tests that use it, passes the devbox storage settings to each run, and reads the index from this machine through a port-forward (`index_query`). It needs the devbox up, with `devbox/setup.sh` applied. Pod-side tasks live in `tests/devbox/pod_tasks.py`, which imports only what the task image carries.
- **Pinata:** calls the real API with the key in `tests/.secrets/pinata_jwt` (`tests/pinata/conftest.py`), and fails without it. Pinata-client tests that don't call the API are in `tests/utils/`.
- **Postgres:** the unit tier's index tests, imported into `tests/postgres/` and run against a throwaway Postgres container that `tests/postgres/conftest.py` starts once per session and removes. Its `index` fixture overrides the SQLite one, and each test starts from a dropped table. A test that depends on SQLite's own behaviour stays out of the import list. Fails without Docker.

A test never skips for a missing tool or service. Outside its tier it's deselected; inside it, a missing tool or an unreachable devbox fails the test, so a run can't pass by testing nothing. Running a workflow locally, outside the tests, needs its tools on your own PATH; nothing here requires them.

## Test Layout

```
tests/
├── conftest.py      # Flyte init, no PINATA_JWT, an empty store per test, the seeded fixture store
├── fixtures/        # Test data by domain, plus seed.py
├── assets/          # unit: asset types, assemble()
├── notebooks/       # unit: every notebook imports and parses
├── unit/            # unit: everything else that runs on Python alone
├── utils/           # unit: src/stargazer/utils/, no external API calls
├── tasks/           # tasks: one directory per task domain, run in the task's image
├── devbox/          # devbox: anything that needs a cluster
├── pinata/          # pinata: the real Pinata API
└── postgres/        # postgres: the index tests against a Postgres container
```

## Isolation (`tests/conftest.py`)

Three things hold for every test, so none of them is set up per test:

- **Flyte is initialized once.** A session-scoped autouse fixture calls `init_flyte()` (`stargazer.config`).
- **No public tier.** `PINATA_JWT` is stripped before anything imports `stargazer`, so no storage client can reach Pinata. The pinata tier's own conftest sets it back from `tests/.secrets/pinata_jwt` for each of its tests.
- **An empty store per test.** `isolated_storage` (autouse) points `stargazer.utils.storage.default_client` at a `StorageClient` whose store, index and cache live under the test's `tmp_path`, and unsets `STARGAZER_OWNER`. Nothing reads or writes `~/.stargazer`. A test that needs its own client builds one with `make_client(root, cache, public, gateway)`, and `FakePublicTier` stands in for Pinata's public network (records in memory, bytes served from a local gateway directory). The devbox tier replaces this fixture with a no-op: its tests store on the devbox.

## Task Test Template

```python
# tests/tasks/{domain}/test_{tool}.py
"""Tests for the {task_name} task."""

from pathlib import Path

import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.assets import {InputType}, {OutputType}
from stargazer.tasks.{domain}.{tool} import {task_name}


@pytest.mark.asyncio
async def test_{task_name}_stores_its_output(fixtures_db):
    """{task_name} stores a {OutputType} linked to its input."""
    input_asset = {InputType}(path=GENERAL_FIXTURES_DIR / "{fixture_file}", sample_id="S1")

    fixtures_db()  # outputs go to an empty per-test store

    result = await {task_name}(input_asset)

    assert isinstance(result, {OutputType})
    assert (result.sample_id, result.tool) == ("S1", "{tool}")
    assert (await result.fetch()).exists()


@pytest.mark.asyncio
async def test_{task_name}_missing_input_fails():
    """A missing input file fails loudly."""
    with pytest.raises((FileNotFoundError, RuntimeError)):
        await {task_name}({InputType}(path=Path("/nonexistent/file")))
```

A task test calls the task directly and awaits it, which runs the function in this process and returns its value.

- **Inputs come from fixture files.** An asset built with a local `path` and no CID is used in place by `fetch()`, so the fixture never has to be stored first. The fixture directories are `GENERAL_FIXTURES_DIR`, `GATK_FIXTURES_DIR` and `SCRNA_FIXTURES_DIR` in `conftest.py`.
- **Outputs go through real storage.** `update()` stores them in the test's store and index, so a test can `fetch()` them back, or `assemble()` for them.
- **`asyncio_mode = "auto"`** is set in `pyproject.toml`; the `@pytest.mark.asyncio` marker is optional.

Task tests run in the task's image:

```bash
uv run --all-extras python cli/docker_task_tests.py tests/tasks/{domain}/test_{tool}.py
```

## The Seeded Fixture Store (`fixtures_db`)

Some tests need inputs as stored records with real CIDs and companion links: an alignment whose index comes along on `fetch()`, a reference found by `assemble()`. `seeded_client` loads every fixture file into one store once per session (`tests/fixtures/seed.py`, with the metadata and `*_cid` links the task tests query for).

`fixtures_db` is two-phase. Requesting it points the default client at the seeded store, so the test can query it and build its inputs. Calling the function it returns (the checkout) switches to an empty per-test store, so the task's outputs never land in the shared seeded one. Always call the checkout before the task.

## Running Through Flyte

Calling a task directly skips Flyte's serialization of its inputs and outputs. To test that path, run the task through Flyte: `flyte.with_runcontext(mode="local").run(task, **inputs)` runs it in this process; `flyte.run(...)` submits it wherever `init_flyte()` points. Either returns a run; `.wait()` for it, and `.outputs()` is a tuple of the task's outputs, so a single output is `.outputs()[0]`. The devbox tier's `devbox_run` fixture (`tests/devbox/conftest.py`) submits this way with the devbox's storage settings, and raises when the run failed.

## Workflow Tests

A workflow is tested where its tasks run. One whose tasks need tools off this machine needs a cluster, so it's devbox-tier: the test seeds inputs from a pod with `devbox_run`, runs the workflow, and checks its output from another pod. Code that runs in the pods lives in `tests/devbox/pod_tasks.py` and imports only what the task image carries.

## Unit Tests

Tests of plain Python (assets, storage, the app tier, the registry) go in the unit-tier directory for their package and need no tools. App routes are tested with FastAPI's `TestClient`; swap module attributes (clients, `config.*`) with `monkeypatch` rather than patching the environment.

## Test Asset Generation

When a test needs a real bioinformatics file, generate it with the tool in the task's image, never on the dev machine, and commit it under `tests/fixtures/<domain>/`:

```bash
docker run --rm --platform linux/amd64 -v "$PWD/tests/fixtures/<domain>:/data" <task image> \
  <tool> <args> /data/<file>
```

`uv run --all-extras python cli/docker_task_tests.py` prints the image it builds. Add a stored copy, with its metadata and `*_cid` links, to `tests/fixtures/seed.py` when tests need to query for it.

## Pytest Configuration

`pyproject.toml` sets `asyncio_mode = "auto"`, `--strict-markers`, and `-m unit` as the default selection. The only markers are the five tiers (`unit`, `tasks`, `devbox`, `pinata`, `postgres`), applied by directory; an unregistered marker such as `slow` is an error.

## Assertions Guidelines

1. **Be Specific**: Assert exact values — fields, file names, record counts
2. **Check Types**: Verify return types match expectations
3. **Validate Files**: `fetch()` the output and check it exists and has the content you expect
4. **Never a None-pass**: if the test would still pass when the code returns `None`, rewrite it

## What to Test

### For Tasks
- ✅ Basic functionality with valid input
- ✅ Input validation and error handling
- ✅ Expected output files are created
- ✅ Output format/content is correct
- ✅ Edge cases (empty input, missing files, etc.)

### For Workflows
- ✅ End-to-end pipeline with real data
- ✅ Output format validation
- ✅ Intermediate results are passed correctly
- ✅ Pipeline handles errors gracefully

## What NOT to Test

- ❌ Implementation details of external tools
- ❌ Flyte framework internals
- ❌ Every possible edge case (focus on common scenarios)

## Running Tests

Each tier's command is in the [tier table](#test-tiers). Paths or `-k` pick a subset:

```bash
uv run --all-extras python cli/docker_task_tests.py tests/tasks/<domain>/test_<tool>.py
uv run --all-extras python cli/docker_task_tests.py -k <name>
```

`pytest tests/tasks/` on its own selects nothing: the default `-m unit` deselects that tier.

## Style Requirements

1. Use descriptive test names: `test_{what}_does_{expected}`
2. Group related tests in classes
3. Use fixtures for setup, not setup/teardown methods
4. Tests should be self-documenting

## Report

Name each test's tier and the command that runs it, and report the run: each new test failed for the expected reason, then passed.

## Don't

- Don't write overly complex tests
- Don't test implementation details
- Don't skip input validation tests
- Don't skip a test for a missing tool or service — it fails inside its tier
- Don't add markers; the tier comes from the directory
- Don't use relative imports - use `from stargazer.{module}`
