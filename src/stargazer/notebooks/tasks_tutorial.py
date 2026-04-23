"""
### Stargazer tasks and workflows tutorial.

Picks up the `SampleSheet` asset from `assets_tutorial` and walks through
defining a Flyte task that consumes it, composing that task into a
fan-out workflow, and the local→remote execution toggle that needs no
code changes.

spec: [docs/architecture/tasks.md](../../docs/architecture/tasks.md)
"""

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    """Imports and Flyte init."""
    import asyncio
    import csv
    import json
    import tempfile
    from dataclasses import dataclass
    from pathlib import Path
    from typing import ClassVar

    import marimo as mo
    import flyte

    flyte.init_from_config()

    mo.md(
        """
        # Stargazer Tasks & Workflows

        This notebook builds on `assets_tutorial.py`. We have a typed
        `SampleSheet` asset; now we'll wrap a real piece of work
        around it.

        The plan:

        1. Re-define `SampleSheet` and add a `CohortSummary` output
           type.
        2. Define a Flyte task that consumes a `SampleSheet` and emits
           a `CohortSummary`.
        3. Compose that task into a fan-out workflow.
        4. Run everything locally.
        5. Flip a single config setting and run the *same code* on a
           remote Flyte cluster.

        Step 5 is the payoff. The whole asset/task/workflow stack is
        designed so notebook iteration and production runs share one
        codebase.
        """
    )
    return ClassVar, Path, asyncio, csv, dataclass, flyte, json, mo, tempfile


@app.cell
def _(mo):
    """Section 1 — recap the SampleSheet asset."""
    mo.md(
        """
        ## 1. Two assets: `SampleSheet` (input) and `CohortSummary` (output)

        Re-defining `SampleSheet` here so this notebook stands alone,
        plus a tiny `CohortSummary` output type. Notice
        `sample_sheet_cid` on the summary — that's the **companion
        pattern** from the asset tutorial in action: any
        `CohortSummary` knows which `SampleSheet` produced it, so
        `sheet.fetch()` will pull the summary alongside.
        """
    )
    return


@app.cell
def _(ClassVar, dataclass):
    """Define SampleSheet and CohortSummary."""
    from stargazer.assets.asset import Asset

    @dataclass
    class SampleSheet(Asset):
        """CSV of per-sample metadata for a cohort."""

        _asset_key: ClassVar[str] = "sample_sheet"
        cohort_id: str = ""
        n_samples: int = 0
        organism: str = ""

    @dataclass
    class CohortSummary(Asset):
        """JSON summary of a cohort: per-organism counts and totals."""

        _asset_key: ClassVar[str] = "cohort_summary"
        cohort_id: str = ""
        n_samples: int = 0
        n_organisms: int = 0
        sample_sheet_cid: str = ""

    return CohortSummary, SampleSheet


@app.cell
def _(mo):
    """Section 2 — what is a task."""
    mo.md(
        """
        ## 2. What's a Flyte task?

        A Flyte task is the unit of work the orchestrator schedules.
        In Flyte v2 it's just a Python function — sync or async —
        attached to a `TaskEnvironment` via `@env.task`:

        ```python
        env = flyte.TaskEnvironment("tutorial")

        @env.task
        async def summarize_cohort(sheet: SampleSheet) -> CohortSummary:
            ...
        ```

        The things worth knowing for Stargazer:

        - **The environment defines the container.** Image, CPU,
          memory, env vars, secrets — all pinned by the
          `TaskEnvironment`. Every task attached to `scrna_env` runs
          in the same scanpy image; every task attached to `gatk_env`
          runs in the GATK image. New workload, new env.
        - **Typed signatures cross the wire.** Inputs and outputs are
          serialized through their declared types — for us that's
          `Asset` subclasses via `to_keyvalues()` / `from_keyvalues()`.
          A task called remotely receives the same typed object it
          would have received locally.
        - **Tasks call tasks.** There is no `@workflow` decorator in
          v2 — a "workflow" is a task whose body awaits other tasks.
          Fan-out is just `asyncio.gather(...)` over task calls.
        - **Same function, two execution shapes.** `await fn(...)`
          runs it in-process for notebook iteration;
          `flyte.run(fn, ...)` (or
          `flyte.with_runcontext(mode="local").run(fn, ...)`) goes
          through the full Flyte machinery — caching, retries,
          remote scheduling.

        Full reference:
        [Flyte v2 — Core concepts: Tasks](https://www.union.ai/docs/v2/flyte/user-guide/core-concepts/tasks/).

        For this tutorial we'll spin up a minimal `TaskEnvironment`
        inline. In production code these live in
        `stargazer/config.py` alongside `scrna_env` and `gatk_env`.
        """
    )
    return


@app.cell
def _(flyte):
    """Define a lightweight task environment for the tutorial."""
    tutorial_env = flyte.TaskEnvironment(
        name="tutorial",
        description="Lightweight env for the tasks tutorial notebook.",
        resources=flyte.Resources(cpu=1, memory="512Mi"),
    )
    return (tutorial_env,)


@app.cell
def _(mo):
    """Section 3 — define a task."""
    mo.md(
        """
        ## 3. Define `summarize_cohort`

        The task does one job: read the CSV the `SampleSheet` points
        at, count rows and unique organisms, write a JSON file, and
        publish a `CohortSummary` asset that links back to its input.

        Notice the I/O shape:

        - **Input is typed**: `sheet: SampleSheet`. The task can't be
          called with the wrong kind of asset.
        - **Output is typed**: `-> CohortSummary`. Downstream tasks
          consuming the result get the same guarantee.
        - **Storage is automatic**: `await sheet.fetch()` materializes
          the CSV; `await summary.update(path=..., **fields)` uploads
          the new JSON and assigns its CID. No manual path juggling.
        """
    )
    return


@app.cell
def _(CohortSummary, Path, SampleSheet, csv, json, tutorial_env):
    """The summarize_cohort task."""

    @tutorial_env.task
    async def summarize_cohort(sheet: SampleSheet) -> CohortSummary:
        """Count samples and unique organisms in a cohort sample sheet."""
        await sheet.fetch()

        with sheet.path.open() as _fh:
            rows = list(csv.DictReader(_fh))
        organisms = sorted({r["organism"] for r in rows if r.get("organism")})

        out_path = Path(sheet.path).parent / f"{sheet.cohort_id}_summary.json"
        out_path.write_text(
            json.dumps(
                {
                    "cohort_id": sheet.cohort_id,
                    "n_samples": len(rows),
                    "organisms": organisms,
                },
                indent=2,
            )
        )

        summary = CohortSummary()
        await summary.update(
            path=out_path,
            cohort_id=sheet.cohort_id,
            n_samples=len(rows),
            n_organisms=len(organisms),
            sample_sheet_cid=sheet.cid,
        )
        return summary

    return (summarize_cohort,)


@app.cell
def _(mo):
    """Section 4 — make some inputs."""
    mo.md(
        """
        ## 4. Spin up some inputs

        We need a few real `SampleSheet` assets to feed the task.
        Building three tiny cohorts and uploading them via
        `update()` — same flow the asset tutorial walked through.
        """
    )
    return


@app.cell
async def _(Path, SampleSheet, csv, mo, tempfile):
    """Build three cohort SampleSheets and upload them."""
    _tmpdir = Path(tempfile.mkdtemp(prefix="stargazer_tasks_tutorial_"))

    _cohorts = [
        ("alpha", [("a1", "human"), ("a2", "human"), ("a3", "human")]),
        ("beta", [("b1", "human"), ("b2", "mouse"), ("b3", "mouse")]),
        ("gamma", [("g1", "human"), ("g2", "human")]),
    ]

    sheets = []
    for _cohort_id, _samples in _cohorts:
        _csv_path = _tmpdir / f"{_cohort_id}.csv"
        with _csv_path.open("w", newline="") as _fh:
            _w = csv.writer(_fh)
            _w.writerow(["sample_id", "organism"])
            _w.writerows(_samples)
        _sheet = SampleSheet()
        await _sheet.update(
            path=_csv_path,
            cohort_id=f"tasks_tutorial_{_cohort_id}",
            n_samples=len(_samples),
            organism="mixed",
        )
        sheets.append(_sheet)

    mo.vstack(
        [
            mo.md(f"Created **{len(sheets)}** cohort sample sheets:"),
            mo.ui.table(
                [
                    {
                        "cohort_id": _s.cohort_id,
                        "n_samples": _s.n_samples,
                        "cid": _s.cid,
                    }
                    for _s in sheets
                ],
                selection=None,
            ),
        ]
    )
    return (sheets,)


@app.cell
def _(mo):
    """Section 5 — run the task locally."""
    mo.md(
        """
        ## 5. Run `summarize_cohort` locally

        `flyte.with_runcontext(mode="local").run(...)` executes the
        task in this Python process while still going through the
        Flyte machinery (caching, retries, output handling). Equivalent
        to running it on a remote cluster, just with the worker being
        you.

        For quick notebook iteration `await summarize_cohort(sheet)`
        also works and skips the Flyte runtime entirely. Same function,
        two execution shapes — both are useful.
        """
    )
    return


@app.cell
async def _(mo, sheets, summarize_cohort):
    """Run the task on the first cohort."""
    first_summary = await summarize_cohort(sheets[0])
    mo.md(
        f"""
        Direct `await summarize_cohort(sheets[0])` returned a
        `{type(first_summary).__name__}`:

        - `cohort_id` → `{first_summary.cohort_id!r}`
        - `n_samples` → `{first_summary.n_samples}`
        - `n_organisms` → `{first_summary.n_organisms}`
        - `sample_sheet_cid` → `{first_summary.sample_sheet_cid}` ← companion link
        - `cid` → `{first_summary.cid}` ← summary's own CID
        """
    )
    return


@app.cell
def _(mo):
    """Section 6 — workflow."""
    mo.md(
        """
        ## 6. Compose into a workflow

        Flyte v2 doesn't have a separate `@workflow` decorator —
        **workflows are tasks that call other tasks**. That means the
        same `@env.task` decorator, with a body that orchestrates other
        tasks instead of doing the work itself.

        Here's a workflow that fans `summarize_cohort` out across many
        cohorts in parallel using `asyncio.gather`:
        """
    )
    return


@app.cell
def _(CohortSummary, SampleSheet, asyncio, summarize_cohort, tutorial_env):
    """Define the audit_cohorts workflow."""

    @tutorial_env.task
    async def audit_cohorts(sheets: list[SampleSheet]) -> list[CohortSummary]:
        """Summarize many cohorts in parallel and return all results."""
        return list(await asyncio.gather(*[summarize_cohort(s) for s in sheets]))

    return (audit_cohorts,)


@app.cell
async def _(audit_cohorts, mo, sheets):
    """Run the workflow."""
    summaries = await audit_cohorts(sheets)

    mo.vstack(
        [
            mo.md(
                f"Ran `audit_cohorts(sheets)` and got back "
                f"**{len(summaries)}** `CohortSummary` instances. "
                "Each task ran concurrently."
            ),
            mo.ui.table(
                [
                    {
                        "cohort_id": _s.cohort_id,
                        "n_samples": _s.n_samples,
                        "n_organisms": _s.n_organisms,
                        "summary_cid": _s.cid,
                    }
                    for _s in summaries
                ],
                selection=None,
            ),
        ]
    )
    return


@app.cell
def _(mo):
    """Section 7 — the superpower."""
    mo.md(
        """
        ## 7. The superpower: local → remote, no code changes

        Everything above ran on this machine. The exact same Python
        code runs on a remote Flyte cluster. The only difference is
        configuration.

        ### Today's `.flyte/config.yaml` (local)

        ```yaml
        image:
          builder: local
        local:
          persistence: true
        ```

        ### To run remotely, point at a Flyte cluster

        ```yaml
        admin:
          endpoint: dns:///flyte.your-org.com
          insecure: false
        platform:
          org: your-org
          project: stargazer
          domain: production
        ```

        That's it. With that file in place:

        ```python
        # Local (what we did above)
        result = await audit_cohorts(sheets)

        # Remote — same task, packaged and shipped to the cluster
        run = flyte.run(audit_cohorts, sheets=sheets)
        run.wait()
        result = run.outputs()
        print(run.url)   # → live UI for the run
        ```

        What happens behind the scenes when you flip to remote:

        - The task body is **packaged into a container** built from
          `tutorial_env.image` (or `scrna_env.image` for real
          workloads), pushed to a registry.
        - Inputs are **serialized via the typed Asset interface** —
          `to_keyvalues()` turns the `SampleSheet` into a flat dict;
          the worker container gets the CIDs and `await sheet.fetch()`
          pulls the bytes from IPFS/Pinata.
        - The fan-out you wrote with `asyncio.gather` becomes
          **N parallel containers** scheduled across the cluster, each
          summarizing one cohort.
        - The CohortSummary outputs are **uploaded with their CIDs**
          and become available to the next task without any path
          juggling — the same content-addressed flow you saw locally.

        This is why we paid the upfront cost of typed assets and
        content addressing: the orchestrator can move the work
        anywhere because the data and metadata are self-describing.
        """
    )
    return


@app.cell
def _(mo):
    """Section 8 — recap."""
    mo.md(
        """
        ## Recap

        | What you did | What you got |
        |--------------|--------------|
        | `@tutorial_env.task` on a function | A unit of work Flyte can run anywhere |
        | Typed `SampleSheet` in, `CohortSummary` out | Self-describing I/O, automatic storage |
        | `await summarize_cohort(sheet)` | In-process iteration speed |
        | `flyte.with_runcontext(mode="local").run(...)` | Same task through the full Flyte machinery |
        | Workflow = task that awaits other tasks | Composition with no special syntax |
        | `asyncio.gather` inside the workflow | Parallel fan-out, scheduled by Flyte |
        | One config swap → `flyte.run(...)` | The same code running on remote workers |

        Production Stargazer pipelines (`scrna_clustering_pipeline`,
        `germline_short_variant_discovery`) follow exactly this shape
        — typed assets in, typed assets out, fan-out with
        `asyncio.gather`, executed locally during development and on
        the cluster in production.
        """
    )
    return


if __name__ == "__main__":
    app.run()
