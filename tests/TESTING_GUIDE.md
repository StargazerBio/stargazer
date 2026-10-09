# Testing Flyte v2 Tasks with Pytest

## Summary

How Stargazer's tests are organized and how a Flyte v2 task is tested here: which tier a test belongs to, how it gets an isolated store, and how it calls a task.

## Test Tiers

Every top-level directory under `tests/` belongs to exactly one tier, and its tests carry that tier's marker. The mapping is `TIERS` in `tests/conftest.py`; a new directory has to be added there, or the run stops with an error naming it. A bare `pytest` run is the unit tier (`addopts` in `pyproject.toml`); `-m` picks another.

| Tier | Marker | Directories | Where it runs | When | Command |
|------|--------|-------------|---------------|------|---------|
| Unit | `unit` | `assets/`, `notebooks/`, `unit/`, `utils/` | This venv | Every commit (pre-commit) | `uv run --all-extras pytest` |
| Tasks | `tasks` | `tasks/` | Each task's image, x86_64 | When you add or change a task | `uv run --all-extras python cli/docker_task_tests.py` |
| Devbox | `devbox` | `devbox/` | The local devbox | When a change reaches the cluster | `uv run --all-extras pytest -m devbox` |
| Pinata | `pinata` | `pinata/` | Against the real Pinata API | When the Pinata client changes | `uv run --all-extras pytest -m pinata` |

- **Unit:** cheap tests that run on Python alone: the asset types, the app tier, storage and the index, the notebook smoke tests. `--all-extras` because the notebook smoke tests need the `notebook` extra and the app tests `landing`.
- **Tasks:** every test of a task, in the image that task runs in. `tests/tasks/<domain>` runs in its domain's image (`IMAGES` in `cli/docker_task_tests.py`): `gatk/` and `general/` in `gatk_env`'s, which carries gatk, bwa, bwa-mem2 and samtools, and `scrna/` in `scrna_env`'s. So a task test checks what a pod gets, and no one installs the tools. The runner builds each image as a task pod gets it, with the project installed, and mounts only `tests/` and `pyproject.toml`, so a source change builds the images again before the tests run. x86_64 like Union, emulated on Apple silicon. Paths or `-k` pick a subset, such as `tests/tasks/gatk/test_sort_sam.py`.
- **Devbox:** anything that needs a cluster: deploying the dashboard, running workflows across pods, the devbox's object store and index. The session deploys the dashboard itself and passes the devbox storage settings to each run. It needs the devbox up, with `cli/devbox-setup.sh` applied. Pod-side tasks live in `tests/devbox/pod_tasks.py`, which imports only what the task image carries.
- **Pinata:** calls the real API with the key in `tests/.secrets/pinata_jwt` (`tests/pinata/conftest.py`), and fails without it. Pinata-client tests that don't call the API are in `tests/utils/`.

A test never skips for a missing tool or service. Outside its tier it's deselected; inside it, a missing tool or an unreachable devbox fails the test, so a run can't pass by testing nothing. Running a workflow locally, outside the tests, needs its tools on your own PATH; nothing here requires them.

## Isolation (`tests/conftest.py`)

Three things hold for every test, so none of them is set up per test:

- **Flyte is initialized once.** A session-scoped autouse fixture calls `flyte.init_from_config()`.
- **No public tier.** `PINATA_JWT` is stripped before anything imports `stargazer`, so no storage client can reach Pinata. The pinata tier's own conftest sets it back from `tests/.secrets/pinata_jwt` for each of its tests.
- **An empty store per test.** `isolated_storage` (autouse) points `stargazer.utils.storage.default_client` at a `StorageClient` whose store, index and cache live under the test's `tmp_path`, and unsets `STARGAZER_OWNER`. Nothing reads or writes `~/.stargazer`. The devbox tier replaces this fixture with a no-op: its tests store on the devbox.

## Calling a Task

A task test calls the task directly and awaits it, which runs the function in this process and returns its value:

```python
import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.assets import Reference, ReferenceIndex
from stargazer.tasks.general.samtools import samtools_faidx


@pytest.mark.asyncio
async def test_samtools_faidx(fixtures_db):
    """samtools faidx stores a .fai index of the reference."""
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

    fixtures_db()  # task outputs go to an empty store

    result = await samtools_faidx(ref)

    assert isinstance(result, ReferenceIndex)
    assert (result.tool, result.build) == ("samtools_faidx", "GRCh38")
    assert result.path.name.endswith(".fai")
    assert (await result.fetch()).exists()
```

- **Inputs come from fixture files.** An asset built with a local `path` and no CID is used in place by `fetch()`, so the fixture never has to be stored first. The fixture directories are `GENERAL_FIXTURES_DIR`, `GATK_FIXTURES_DIR` and `SCRNA_FIXTURES_DIR` in `conftest.py`.
- **Outputs go through real storage.** `update()` stores them in the test's store and index, so a test can `fetch()` them back, or `assemble()` for them.
- **`asyncio_mode = "auto"`** is set in `pyproject.toml`; the `@pytest.mark.asyncio` marker is optional.

## The Seeded Fixture Store (`fixtures_db`)

Some tests need inputs as stored records with real CIDs and companion links: an alignment whose index comes along on `fetch()`, a reference found by `assemble()`. `seeded_client` loads every fixture file into one store once per session (`tests/fixtures/seed.py`, with the metadata and `*_cid` links the task tests query for).

`fixtures_db` is two-phase. Requesting it points the default client at the seeded store, so the test can query it and build its inputs. Calling the function it returns (the checkout) switches to an empty per-test store, so the task's outputs never land in the shared seeded one.

## Running Through Flyte

Calling a task directly skips Flyte's serialization of its inputs and outputs. To test that path, run the task through Flyte: `flyte.with_runcontext(mode="local").run(task, **inputs)` runs it in this process; `flyte.run(...)` submits it wherever `flyte.init_from_config()` points. Either returns a run; `.wait()` for it, and `.outputs()` is a tuple of the task's outputs, so a single output is `.outputs()[0]`. The devbox tier's `devbox_run` fixture (`tests/devbox/conftest.py`) submits this way with the devbox's storage settings, and raises when the run failed.

## Writing a Good Test

1. **Assert literal values.** Check the output's fields and its file, not only its type. A test that would still pass if the task returned `None` tests nothing.
2. **Confirm it fails first,** for the reason you expect (missing behavior), not an import error or a broken fixture.
3. **Use the fixture files,** and generate a new fixture in the task's image (`docker run --platform linux/amd64 <image> ...`) when it needs a bioinformatics tool, rather than installing the tool.
4. **Call the checkout before the task** in a `fixtures_db` test, so outputs never touch the shared seeded store.
5. **Fail, don't skip.** A missing tool, key or service inside its tier fails the test.
