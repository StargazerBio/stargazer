"""
### Notebook controls for choosing where a run goes.

`run_location()` is a control a notebook drops into a cell, set to "On this
machine" or "On the cluster", and `dispatch()` runs a task or workflow wherever
it's set. Reading a control's value in the cell that made it is an error in
marimo, so the control and the dispatch go in separate cells, and changing the
control re-runs the dispatching cell:

    where = run_location()
    where

    summaries = await dispatch(where, audit_cohorts, sheets=sheets)

A cluster run's code bundle comes from where the dispatched task's module was
imported from: the notebook's own directory when the notebook defining it is the
one running, as a workspace notebook in its pod is, or the package root for one
imported by its dotted name. The task has to be importable there, which a task
defined in a regular cell isn't: it goes in an `@app.function`.

A module of its own rather than part of the package `__init__`, because it
imports marimo and the dashboard imports `stargazer.notebooks` without it.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import inspect
from pathlib import Path

import flyte
import marimo as mo
from flyte._initialize import get_init_config, init_config_context


def run_location() -> mo.ui.radio:
    """The control for where a notebook's runs go, starting on this machine.

    Its value is the Flyte run mode the choice stands for, which is what
    `dispatch` passes on.
    """
    return mo.ui.radio(
        options={"On this machine": "local", "On the cluster": "remote"},
        value="On this machine",
        inline=True,
        label="Run",
    )


async def dispatch(location: mo.ui.radio, task: flyte.TaskTemplate, /, **inputs):
    """Run `task` with `inputs` where `location` says, and return its output.

    Waits for the run to finish either way, so the result is the value awaiting
    the task directly would give. Handles tasks with one output. "On the
    cluster" asks for a remote run outright: `flyte.run` would quietly run
    in-process when no cluster is configured. It bundles the run's code from
    `task`'s own root (`_bundle_root`), and returns the output as the type
    `task` declares.
    """
    runner = flyte.with_runcontext(mode=location.value)
    if location.value == "local":
        run = await runner.run.aio(task, **inputs)
        await run.wait.aio()
        return (await run.outputs.aio())[0]
    # A context-scoped override, so samples dispatched together with
    # `asyncio.gather` each keep their own.
    with init_config_context(get_init_config().replace(root_dir=_bundle_root(task))):
        run = await runner.run.aio(task, **inputs)
    await run.wait.aio()
    # A remote run's `outputs()` rebuilds each value from its stored schema, as
    # a look-alike class without the real one's methods (an asset's `fetch`).
    outputs = await run.typed_outputs.aio(task.native_interface.outputs)
    return next(iter(outputs.values()))


def _bundle_root(task: flyte.TaskTemplate) -> Path:
    """The directory `task`'s module was imported from.

    A module named `a.b.c` sits two directories below it, and a top-level one,
    the running notebook (`__main__`) included, sits in it.
    """
    module = inspect.getmodule(task.func)
    return Path(module.__file__).absolute().parents[module.__name__.count(".")]
