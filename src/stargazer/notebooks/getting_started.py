"""
### Getting Started with Stargazer.

Interactive notebook for exploring tasks, running workflows,
and visualizing results.

spec: [docs/architecture/notebook.md](../../docs/architecture/notebook.md)
"""

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    """Render the introductory header and project overview."""
    import marimo as mo

    mo.md(
        """
        # Stargazer

        Interactive bioinformatics workflows powered by
        [Flyte v2](https://www.union.ai/docs/v2/flyte/) and
        [IPFS](https://ipfs.io/) storage.

        This notebook demonstrates how to explore available tasks,
        run them, and visualize results. Everything here runs the
        same code that powers production workflows — the only
        difference is the execution context.
        """
    )
    return (mo,)


@app.cell
def _(mo):
    """Initialize Flyte and load the task registry."""
    import flyte

    flyte.init_from_config()

    from stargazer.registry import TaskRegistry

    _registry = TaskRegistry()

    task_catalog = _registry.to_catalog(category="task")
    workflow_catalog = _registry.to_catalog(category="workflow")

    mo.md("## Available Tasks")
    return task_catalog, workflow_catalog


@app.cell
def _(mo, task_catalog):
    """Display the task catalog as an interactive table."""
    _rows = [
        {
            "name": t["name"],
            "description": t["description"],
            "params": ", ".join(f"{p['name']}: {p['type']}" for p in t["params"]),
            "outputs": ", ".join(o["type"] for o in t["outputs"]),
        }
        for t in task_catalog
    ]
    task_table = mo.ui.table(
        _rows,
        label="Tasks",
        selection=None,
    )
    task_table
    return


@app.cell
def _(mo, workflow_catalog):
    """Display the workflow catalog as an interactive table."""
    _rows = [
        {
            "name": w["name"],
            "description": w["description"],
            "params": ", ".join(f"{p['name']}: {p['type']}" for p in w["params"]),
        }
        for w in workflow_catalog
    ]
    workflow_table = mo.ui.table(
        _rows,
        label="Workflows",
        selection=None,
    )
    mo.md("## Available Workflows")
    workflow_table
    return


@app.cell
def _(mo):
    """Show usage examples for running tasks and workflows."""
    mo.md(
        """
        ## Running Tasks

        Import and call any task directly. In a local context, tasks
        run on your machine. Switch to a remote Flyte cluster by
        changing the config at `.flyte/config.yaml`.

        ```python
        from stargazer.tasks import bwa_mem
        from stargazer.assets import Reference, R1

        ref = Reference(cid="Qm...")
        r1 = R1(cid="Qm...")
        alignment = await bwa_mem(ref=ref, r1=r1)
        ```

        Workflows compose tasks with `asyncio.gather` for parallelism:

        ```python
        from stargazer.workflows import germline_short_variant_discovery

        variants = await germline_short_variant_discovery(
            build="GRCh38",
            sample_ids=["NA12878"],
        )
        ```
        """
    )
    return


@app.cell
def _(mo):
    """Introduce the local storage section."""
    mo.md(
        """
        ## Local Storage

        Query assets already in your local store:
        """
    )
    return


@app.cell
def _(mo):
    """Query and display all assets in local storage."""
    from stargazer.utils.local_storage import default_client

    async def _query_all():
        """Return all assets from the local store."""
        return await default_client.query({})

    import asyncio

    _all_assets = asyncio.get_event_loop().run_until_complete(_query_all())

    if _all_assets:
        _rows = [
            {
                "cid": a.get("cid", ""),
                "asset": a.get("keyvalues", {}).get("asset", ""),
                "path": a.get("path", ""),
            }
            for a in _all_assets
        ]
        mo.ui.table(_rows, label="Local Assets", selection=None)
    else:
        mo.md(
            "_No local assets yet. Upload files or use "
            "`fetch_resource_bundle` to get started._"
        )
    return


if __name__ == "__main__":
    app.run()
