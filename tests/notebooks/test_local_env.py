"""Tests for running a package task in its own environment on this machine."""

from pathlib import Path

import flyte

import stargazer
from stargazer.assets.scrna import AnnData
from stargazer.notebooks import local_env
from stargazer.notebooks.ui import dispatch, run_location
from stargazer.tasks.general.bwa import bwa_mem
from stargazer.tasks.scrna.normalize import normalize

env = flyte.TaskEnvironment(name="local_env_test")
TASKS = Path(stargazer.__file__).parent / "tasks"


@env.task
async def add_one(x: int) -> int:
    """Return `x + 1`."""
    return x + 1


def _host(monkeypatch, platform, *, tools):
    """Make this machine `platform` (a conda subdir) with `tools` on the PATH."""
    monkeypatch.setattr(local_env, "_host_platform", lambda: platform)
    monkeypatch.setattr(
        local_env.shutil,
        "which",
        lambda name: f"/bin/{name}" if name in tools else None,
    )


def test_a_task_runs_from_its_domains_env_header():
    """A task's environment is its domain's `env.py`; `general/` shares gatk's."""
    assert local_env.env_script(normalize) == TASKS / "scrna" / "env.py"
    assert local_env.env_script(bwa_mem) == TASKS / "gatk" / "env.py"


def test_a_package_task_runs_in_pixi_where_its_header_solves(monkeypatch):
    """On a platform its header lists, with pixi installed, the task runs in pixi."""
    _host(monkeypatch, "linux-64", tools={"pixi", "docker"})

    assert local_env.executor(normalize) == "pixi"


def test_docker_runs_a_header_that_doesnt_solve_here(monkeypatch):
    """On a platform its header doesn't list, docker runs the task image instead."""
    _host(monkeypatch, "win-64", tools={"pixi", "docker"})

    assert local_env.executor(normalize) == "docker"


def test_with_neither_a_package_task_runs_in_process(monkeypatch):
    """Without a way to run its environment, the task stays in the kernel."""
    _host(monkeypatch, "win-64", tools={"pixi"})

    assert local_env.executor(normalize) is None


def test_a_task_from_outside_the_package_runs_in_process(monkeypatch):
    """A notebook's own task has no domain environment, so it stays in the kernel."""
    _host(monkeypatch, "linux-64", tools={"pixi", "docker"})

    assert local_env.executor(add_one) is None


def test_the_environment_holds_its_headers_lock(tmp_path, monkeypatch):
    """The installed workspace is the header's, locked by its `env.py.pixi.lock`."""
    monkeypatch.setenv("STARGAZER_LOCAL", str(tmp_path / "local"))

    workspace = local_env.workspace(TASKS / "scrna" / "env.py")

    assert workspace == tmp_path / "local" / "envs" / "scrna"
    assert (workspace / "pixi.lock").read_bytes() == (
        TASKS / "scrna" / "env.py.pixi.lock"
    ).read_bytes()
    assert 'scanpy = ">=1.12"' in (workspace / "pixi.toml").read_text()


def test_the_environment_imports_the_kernels_sdk(tmp_path):
    """The env's own released SDK is shadowed by the kernel's, checkout or installed."""
    overlay = local_env.sdk_overlay(tmp_path)

    assert (overlay / "stargazer").resolve() == Path(stargazer.__file__).parent


async def test_dispatch_on_this_machine_sends_a_package_task_to_its_environment(
    monkeypatch, tmp_path
):
    """`dispatch` hands a package task and its inputs to the environment runner."""
    _host(monkeypatch, "linux-64", tools={"pixi"})
    calls = []

    async def run_in_env(task, inputs):
        """Record the call and return a marker output."""
        calls.append((task, inputs))
        return "ran in its environment"

    monkeypatch.setattr(local_env, "run_in_env", run_in_env)
    adata = AnnData(path=tmp_path / "x.h5ad", sample_id="s1", organism="human")

    assert (
        await dispatch(run_location(), normalize, adata=adata)
        == "ran in its environment"
    )
    assert calls == [(normalize, {"adata": adata})]


def test_mounts_cover_local_storage_and_input_files(monkeypatch, tmp_path):
    """The local store, the index's directory and the scratch space are mounted
    writable at their own paths; an input file elsewhere, read-only; one inside a
    mounted directory or a missing one, not at all."""
    monkeypatch.setenv("STARGAZER_LOCAL", str(tmp_path / "local"))
    monkeypatch.setenv("STARGAZER_STORE_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv("STARGAZER_INDEX_URL", str(tmp_path / "idx" / "index.db"))
    (tmp_path / "data").mkdir()
    inputs = {
        "adata": AnnData(path=tmp_path / "data" / "x.h5ad", sample_id="s1"),
        "n": 3,
        "more": [
            AnnData(path=tmp_path / "local" / "y.h5ad", sample_id="s2"),
            AnnData(path=tmp_path / "gone" / "z.h5ad", sample_id="s3"),
        ],
    }

    assert local_env._mounts(inputs) == [
        f"{tmp_path}/local:{tmp_path}/local",
        f"{tmp_path}/store:{tmp_path}/store",
        f"{tmp_path}/idx:{tmp_path}/idx",
        f"{tmp_path}/data:{tmp_path}/data:ro",
    ]


def test_remote_storage_is_not_mounted(monkeypatch, tmp_path):
    """A bucket store and a database index are reached over the network, not mounted."""
    monkeypatch.setenv("STARGAZER_LOCAL", str(tmp_path / "local"))
    monkeypatch.setenv("STARGAZER_STORE_ROOT", "s3://stargazerbio-users")
    monkeypatch.setenv("STARGAZER_INDEX_URL", "postgresql://db:5432/stargazer")

    assert local_env._mounts({}) == [f"{tmp_path}/local:{tmp_path}/local"]
