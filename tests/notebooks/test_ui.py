"""Tests for the run-location control and `dispatch`."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import flyte
import marimo as mo
from flyte._initialize import get_init_config, init_config_context
from flyte._internal.resolvers.default import DefaultTaskResolver

from stargazer import config
from stargazer.notebooks.ui import dispatch, run_location
from stargazer.tasks.general.samtools import samtools_faidx

env = flyte.TaskEnvironment(name="ui_test")


@env.task
async def add_one(x: int) -> int:
    """Return `x + 1`."""
    return x + 1


def _remote_run(stored, waited=None):
    """A remote run handle whose one output is stored as the text `stored`.

    Like a real one, it decodes outputs only into the types the caller asks for
    (`typed_outputs`); its schema-guessed `outputs()` are look-alikes without the
    real class's methods. Outputs are refused until `waited` is non-empty.
    """
    waited = [True] if waited is None else waited

    async def wait():
        """Mark the run finished."""
        waited.append(True)

    async def typed_outputs(types):
        """Decode each stored output into the type asked for it."""
        if not waited:
            raise RuntimeError("Action is not in a terminal state")
        return {name: kind(stored) for name, kind in types.items()}

    return SimpleNamespace(
        wait=SimpleNamespace(aio=wait),
        typed_outputs=SimpleNamespace(aio=typed_outputs),
    )


def _record_modes(monkeypatch, runner_for):
    """Patch `flyte.with_runcontext` to log each mode, then defer to `runner_for`."""
    modes = []

    def with_runcontext(mode=None, **kwargs):
        """Log the mode asked for."""
        modes.append(mode)
        return runner_for(mode, **kwargs)

    monkeypatch.setattr(flyte, "with_runcontext", with_runcontext)
    return modes


async def test_dispatch_runs_on_this_machine_by_default(monkeypatch):
    """The control starts on this machine, and the task runs in-process."""
    modes = _record_modes(monkeypatch, flyte.with_runcontext)

    assert await dispatch(run_location(), add_one, x=1) == 2
    assert modes == ["local"]


async def test_dispatch_runs_on_the_cluster_when_picked(monkeypatch):
    """Picking the cluster submits a remote run and returns its output once done,
    as the type the task declares."""
    submitted = []
    run = _remote_run("7", waited=[])

    async def submit(task, **inputs):
        """Record what was submitted and hand back the run."""
        submitted.append((task, inputs))
        return run

    modes = _record_modes(
        monkeypatch, lambda mode, **_: SimpleNamespace(run=SimpleNamespace(aio=submit))
    )
    where = mo.ui.radio(options=run_location().options, value="On the cluster")

    assert await dispatch(where, add_one, x=1) == 7
    assert modes == ["remote"]
    assert submitted == [(add_one, {"x": 1})]


async def test_cluster_run_bundles_from_where_the_task_was_imported(
    monkeypatch, tmp_path
):
    """A task from a top-level module outside the package, as a workspace notebook's
    are, goes to the cluster with its own directory as the code bundle's root."""
    (tmp_path / "my_notebook.py").write_text(
        "import flyte\n"
        "env = flyte.TaskEnvironment(name='ui_test_workspace')\n"
        "@env.task\n"
        "async def double(x: int) -> int:\n"
        "    return 2 * x\n"
    )
    spec = importlib.util.spec_from_file_location(
        "my_notebook", tmp_path / "my_notebook.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "my_notebook", module)
    spec.loader.exec_module(module)
    submitted = []

    async def submit(task, **inputs):
        """Record the bundle root and the loader args a submission would record."""
        root = get_init_config().root_dir
        submitted.append((root, DefaultTaskResolver().loader_args(task, root)))
        return _remote_run("4")

    _record_modes(
        monkeypatch, lambda mode, **_: SimpleNamespace(run=SimpleNamespace(aio=submit))
    )
    where = mo.ui.radio(options=run_location().options, value="On the cluster")

    assert await dispatch(where, module.double, x=2) == 4
    assert submitted == [(tmp_path, ["mod", "my_notebook", "instance", "double"])]


async def _bundle_root_of(monkeypatch, task, root):
    """The code bundle's root a cluster dispatch of `task` submits with, given
    `root` as the one `init_flyte()` set."""
    roots = []

    async def submit(task, **inputs):
        """Record the bundle root the submission sees."""
        roots.append(get_init_config().root_dir)
        return _remote_run("chrT")

    _record_modes(
        monkeypatch, lambda mode, **_: SimpleNamespace(run=SimpleNamespace(aio=submit))
    )
    where = mo.ui.radio(options=run_location().options, value="On the cluster")
    with init_config_context(get_init_config().replace(root_dir=root)):
        await dispatch(where, task, ref=None)
    return roots


async def test_an_installed_sdk_task_bundles_from_init_flytes_root(
    monkeypatch, tmp_path
):
    """With the SDK installed, a task imported from it keeps the root `init_flyte()`
    set, the running notebook's folder: its module is in site-packages, which Flyte
    never bundles, and in the task's image already."""
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    workspace = tmp_path / "workspace"

    assert await _bundle_root_of(monkeypatch, samtools_faidx, workspace) == [workspace]


async def test_a_checkout_sdk_task_bundles_from_the_checkouts_source(
    monkeypatch, tmp_path
):
    """From a checkout, a task imported from the SDK carries the checkout's source."""
    source = Path(config.__file__).resolve().parents[1]

    assert await _bundle_root_of(monkeypatch, samtools_faidx, tmp_path) == [source]
