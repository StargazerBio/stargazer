"""Tests for the run-location control and `dispatch`."""

from types import SimpleNamespace

import flyte
import marimo as mo

from stargazer.notebooks.ui import dispatch, run_location

env = flyte.TaskEnvironment(name="ui_test")


@env.task
async def add_one(x: int) -> int:
    """Return `x + 1`."""
    return x + 1


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
    """Picking the cluster submits a remote run and returns its output once done."""
    submitted = []
    waited = []

    async def wait():
        """Mark the run finished."""
        waited.append(True)

    async def outputs():
        """Refuse until the run has finished, as a remote run does."""
        if not waited:
            raise RuntimeError("Action is not in a terminal state")
        return (7,)

    run = SimpleNamespace(
        wait=SimpleNamespace(aio=wait), outputs=SimpleNamespace(aio=outputs)
    )

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
