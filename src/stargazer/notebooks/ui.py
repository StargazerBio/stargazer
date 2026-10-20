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

A module of its own rather than part of the package `__init__`, because it
imports marimo and the dashboard imports `stargazer.notebooks` without it.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import flyte
import marimo as mo


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
    in-process when no cluster is configured.
    """
    run = await flyte.with_runcontext(mode=location.value).run.aio(task, **inputs)
    await run.wait.aio()
    return (await run.outputs.aio())[0]
