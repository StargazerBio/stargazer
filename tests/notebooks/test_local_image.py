"""Tests for running a package task in its own image on this machine."""

import flyte

from stargazer.assets.scrna import AnnData
from stargazer.notebooks import local_image
from stargazer.notebooks.ui import dispatch, run_location
from stargazer.tasks.scrna.normalize import normalize

env = flyte.TaskEnvironment(name="local_image_test")


@env.task
async def add_one(x: int) -> int:
    """Return `x + 1`."""
    return x + 1


def _docker(monkeypatch, path):
    """Make `docker` resolve to `path` on the PATH (None: not installed)."""
    monkeypatch.setattr(local_image.shutil, "which", lambda name: path)


def test_a_package_task_runs_in_its_image_where_docker_is(monkeypatch):
    """With docker on the PATH, a task from the SDK's tasks runs in its image."""
    _docker(monkeypatch, "/usr/bin/docker")

    assert local_image.runs_in_image(normalize) is True


def test_without_docker_a_package_task_runs_in_process(monkeypatch):
    """A hosted pod has no docker, so its package tasks stay in the kernel."""
    _docker(monkeypatch, None)

    assert local_image.runs_in_image(normalize) is False


def test_a_task_from_outside_the_package_runs_in_process(monkeypatch):
    """A task its image doesn't install, as a notebook's own are, stays in-process."""
    _docker(monkeypatch, "/usr/bin/docker")

    assert local_image.runs_in_image(add_one) is False


async def test_dispatch_on_this_machine_sends_a_package_task_to_its_image(
    monkeypatch, tmp_path
):
    """`dispatch` hands a package task and its inputs to the image runner."""
    _docker(monkeypatch, "/usr/bin/docker")
    calls = []

    async def run_in_image(task, inputs):
        """Record the call and return a marker output."""
        calls.append((task, inputs))
        return "ran in image"

    monkeypatch.setattr(local_image, "run_in_image", run_in_image)
    adata = AnnData(path=tmp_path / "x.h5ad", sample_id="s1", organism="human")

    assert await dispatch(run_location(), normalize, adata=adata) == "ran in image"
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

    assert local_image._mounts(inputs) == [
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

    assert local_image._mounts({}) == [f"{tmp_path}/local:{tmp_path}/local"]
