# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "marimo",
#   "matplotlib",
#   "scanpy>=1.12",
#   "anndata",
#   "stargazer",
# ]
#
# [tool.uv.sources]
# stargazer = { path = "/stargazer", editable = true }
# ///
"""
### Stargazer scRNA-seq preprocessing tutorial.

Progressive walkthrough that builds up Stargazer's primitives in the order
a new user encounters them: Asset → Task → Workflow → local execution →
remote execution. Scope is intentionally narrow (preprocessing only) so
the local-vs-remote contrast is the headline lesson; clustering and
parameter sweeps belong in a follow-up tutorial.

spec: [docs/workflows/scrna.md](../../workflows/scrna.md)
"""

import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    """Imports and in-cluster Flyte init."""
    import os
    import time
    import warnings

    warnings.filterwarnings("ignore", message="Variable names are not unique")
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="scanpy")

    import marimo as mo
    import flyte
    import matplotlib.pyplot as plt

    flyte.init_in_cluster(
        project=os.environ["FLYTE_PROJECT"],
        domain=os.environ["FLYTE_DOMAIN"],
    )

    mo.md(
        """
        # Stargazer — scRNA-seq Preprocessing Tutorial

        A guided tour of how Stargazer wraps scanpy in a Flyte v2
        orchestrator. We'll build a four-stage preprocessing pipeline
        — **qc_filter → normalize → select_features → reduce_dimensions** —
        then run the same workflow two ways:

        1. **Locally**, in this notebook pod's own process (blocking).
        2. **Remotely**, submitted to the Flyte cluster, with a URL to
           watch the action as it executes.

        Clustering and interactive parameter sweeps are deferred to a
        follow-up tutorial — here the focus is the local-vs-remote story.
        """
    )
    return flyte, mo, plt, time


@app.cell
def _(mo):
    """Section 1 — What is an Asset?"""
    mo.md(
        """
        ## 1. Assets — Stargazer's Typed I/O

        Every input and output in a Stargazer workflow is an **`Asset`**
        subclass: a small dataclass that wraps a content-addressed
        identifier (`cid`), a local materialization path (`path`), and
        typed metadata fields describing what the file represents.

        For scRNA-seq, the asset is `AnnData`:

        ```python
        @dataclass
        class AnnData(Asset):
            _asset_key: ClassVar[str] = "anndata"
            sample_id: str = ""
            n_obs: int = 0        # cells
            n_vars: int = 0       # genes
            stage: str = ""       # "raw", "qc_filtered", "normalized", ...
            organism: str = ""
            source_cid: str = ""  # provenance: cid of the input asset
        ```

        Two operations on every asset:

        - `await asset.fetch()` — materialize the file at `asset.path`.
        - `assemble(asset="anndata", sample_id=..., ...)` — look up
          assets by metadata across the storage backends.
        """
    )
    return


@app.cell
async def _(mo):
    """Section 2 — Resolve one raw sample, fetching the demo bundle on miss."""
    from stargazer.assets.asset import assemble
    from stargazer.bundles import fetch_bundle

    sample_id = "s1d1"

    async def _resolve():
        """Look up the raw AnnData asset for `sample_id`, or None if missing."""
        hits = await assemble(sample_id=sample_id, asset="anndata", stage="raw")
        return hits[0] if hits else None

    raw_asset = await _resolve()
    if raw_asset is None:
        with mo.status.spinner(title="Fetching scrna_demo bundle..."):
            await fetch_bundle("scrna_demo")
        raw_asset = await _resolve()
    if raw_asset is None:
        mo.stop(True, mo.md(f"Sample `{sample_id}` not in `scrna_demo`."))

    await raw_asset.fetch()
    mo.md(
        f"""
        ## 2. Fetch a Raw Sample

        Resolved one `AnnData` asset for sample **`{raw_asset.sample_id}`**:

        - `cid`: `{raw_asset.cid}`
        - `path`: `{raw_asset.path}`
        - `n_obs`: {raw_asset.n_obs:,} cells
        - `n_vars`: {raw_asset.n_vars:,} genes
        - `stage`: `{raw_asset.stage}`
        - `organism`: `{raw_asset.organism}`

        Calling `await raw_asset.fetch()` has materialized the underlying
        `.h5ad` file on the local filesystem at `path`.
        """
    )
    return (raw_asset,)


@app.cell
def _(mo, plt, raw_asset):
    """Section 3 — Raw QC histograms for the picked sample."""
    import scanpy as sc

    ad = sc.read_h5ad(raw_asset.path)
    ad.var_names_make_unique()
    ad.var["mt"] = ad.var_names.str.startswith("MT-") | ad.var_names.str.startswith(
        "mt-"
    )
    ad.var["ribo"] = ad.var_names.str.startswith(("RPS", "RPL", "Rps", "Rpl"))
    sc.pp.calculate_qc_metrics(ad, qc_vars=["mt", "ribo"], inplace=True, log1p=False)

    fig, axes = plt.subplots(1, 4, figsize=(16, 3.5))
    for ax, key, color, title in zip(
        axes,
        ["n_genes_by_counts", "total_counts", "pct_counts_mt", "pct_counts_ribo"],
        ["#2196F3", "#4CAF50", "#FF5722", "#9C27B0"],
        ["Genes per cell", "Total counts", "% Mitochondrial", "% Ribosomal"],
    ):
        ax.hist(ad.obs[key], bins=50, color=color)
        ax.set_title(f"{raw_asset.sample_id} — {title}")
        ax.set_xlabel(key)
    fig.suptitle("Raw QC Metrics", fontsize=14, fontweight="bold")
    fig.tight_layout()

    mo.vstack(
        [
            mo.md(
                """
                ## 3. Raw Quality Control

                Before any filtering: genes per cell and total counts
                surface low-quality droplets; mitochondrial and ribosomal
                fractions surface stressed or lysed cells. The
                `qc_filter` task below will trim cells exceeding the
                `max_pct_mt` threshold.
                """
            ),
            fig,
        ]
    )
    return


@app.cell
def _(mo):
    """Section 4 — What is a Task?"""
    mo.md(
        """
        ## 4. Tasks — Single-Purpose Units of Work

        A Stargazer task is an `async def` decorated with
        `@scrna_env.task`. It takes typed `Asset` inputs, returns a
        typed `Asset` output, and Flyte handles the rest: caching,
        retries, resource scheduling, and serialization across pod
        boundaries.

        The first stage, `qc_filter`, looks like this:

        ```python
        @scrna_env.task
        async def qc_filter(
            adata: AnnData,
            min_genes: int = 100,
            min_cells: int = 3,
            max_pct_mt: float = 20.0,
            batch_key: str = "",
            organism: str = "human",
        ) -> AnnData:
            import scanpy as sc
            await adata.fetch()
            ad = sc.read_h5ad(adata.path)
            sc.pp.filter_cells(ad, min_genes=min_genes)
            sc.pp.filter_genes(ad, min_cells=min_cells)
            # ...annotate mito/ribo, compute QC metrics, run scrublet...
            ad = ad[ad.obs["pct_counts_mt"] < max_pct_mt]
            ad = ad[~ad.obs["predicted_doublet"]]
            out_path = _storage.default_client.local_dir / "qc_filtered.h5ad"
            ad.write_h5ad(out_path)
            result = AnnData(
                sample_id=adata.sample_id,
                organism=adata.organism,
                source_cid=adata.cid,
            )
            await result.update(out_path, n_obs=ad.n_obs, n_vars=ad.n_vars, stage="qc_filtered")
            return result
        ```

        The other three preprocessing tasks follow the same shape:

        - **`normalize`** — normalize total counts + log-transform; keeps raw counts in `.layers["counts"]`.
        - **`select_features`** — pick the top N highly variable genes.
        - **`reduce_dimensions`** — PCA → neighbors → UMAP.
        """
    )
    return


@app.cell
def _():
    """Section 5 — Compose tasks into a workflow."""
    from stargazer.config import scrna_env
    from stargazer.assets.scrna import AnnData
    from stargazer.tasks.scrna import (
        normalize,
        qc_filter,
        reduce_dimensions,
        select_features,
    )

    @scrna_env.task
    async def preprocess(raw: AnnData, max_pct_mt: float, n_top_genes: int) -> AnnData:
        """QC, normalize, select HVGs, and reduce dimensions for one sample."""
        filtered = await qc_filter(adata=raw, max_pct_mt=max_pct_mt)
        normalized = await normalize(adata=filtered)
        featured = await select_features(adata=normalized, n_top_genes=n_top_genes)
        return await reduce_dimensions(adata=featured)

    return (preprocess,)


@app.cell
def _(mo):
    """Section 5 — narrative for the workflow definition."""
    mo.md(
        """
        ## 5. Compose Tasks into a Workflow

        In Flyte v2 a "workflow" is just a task that calls other tasks
        — no separate `@workflow` decorator. The cell above defines
        `preprocess` as an `@scrna_env.task` that awaits each stage in
        sequence and returns the final `AnnData`.

        Caching is left at the default: a second call with identical
        inputs reuses the cached result instead of recomputing.
        """
    )
    return


@app.cell
def _(flyte, mo, preprocess, raw_asset, time):
    """Section 6 — run preprocess locally (blocking)."""
    with mo.status.spinner(title="Running preprocess locally..."):
        _t0 = time.perf_counter()
        local_run = flyte.with_runcontext(mode="local").run(
            preprocess, raw=raw_asset, max_pct_mt=20.0, n_top_genes=2000
        )
        reduced_local = local_run.outputs()
        _elapsed_local = time.perf_counter() - _t0

    mo.md(
        f"""
        ## 6. Run Locally (Blocking)

        Awaiting `preprocess(...)` directly would just execute it in
        this notebook pod's process with no Flyte run record.
        `flyte.with_runcontext(mode="local").run(...)` exercises the
        same code path as cluster execution — task serialization,
        cache lookups, typed I/O — but stays in-process. The call
        **blocks** until the whole DAG finishes; outputs are available
        immediately.

        Result for **`{reduced_local.sample_id}`** after `{_elapsed_local:.1f}s`:

        - `cid`: `{reduced_local.cid}`
        - `n_obs`: {reduced_local.n_obs:,} cells (filtered)
        - `n_vars`: {reduced_local.n_vars:,} genes
        - `stage`: `{reduced_local.stage}`
        """
    )
    return (reduced_local,)


@app.cell
def _(flyte, mo, preprocess, raw_asset, time):
    """Section 7 — submit preprocess remotely; render URL before waiting."""
    _t0 = time.perf_counter()
    remote_run = flyte.run(preprocess, raw=raw_asset, max_pct_mt=20.0, n_top_genes=2000)

    # Flush the console URL to the cell output *before* blocking on wait()
    # — otherwise the URL would appear only after the run completes.
    mo.output.append(
        mo.md(
            f"""
            ## 7. Run Remotely (URL First, Then Wait)

            `flyte.run(preprocess, ...)` submits the task to the cluster
            and returns a `Run` handle **immediately**. The `.url` deep-links
            into the Flyte console so you can watch the action execute.

            **Watch on console:** [{remote_run.url}]({remote_run.url})

            Waiting for completion below...
            """
        )
    )

    with mo.status.spinner(title="Waiting for remote run..."):
        remote_run.wait()
        reduced_remote = remote_run.outputs()
        _elapsed_remote = time.perf_counter() - _t0

    mo.output.append(
        mo.md(
            f"""
            **Finished in `{_elapsed_remote:.1f}s`.** Result is content-identical
            to the local run when caching is on and inputs match.

            - `cid`: `{reduced_remote.cid}`
            - `n_obs`: {reduced_remote.n_obs:,} cells
            - `n_vars`: {reduced_remote.n_vars:,} genes
            """
        )
    )
    return (reduced_remote,)


@app.cell
async def _(mo, plt, reduced_remote):
    """Section 8 — visualize the UMAP from the remote run."""
    import scanpy as sc

    await reduced_remote.fetch()
    ad = sc.read_h5ad(reduced_remote.path)

    umap = ad.obsm["X_umap"]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(umap[:, 0], umap[:, 1], s=2, alpha=0.6, c="#3F51B5")
    ax.set_xlabel("UMAP1")
    ax.set_ylabel("UMAP2")
    ax.set_title(f"{reduced_remote.sample_id} — UMAP after preprocessing")
    fig.tight_layout()

    mo.vstack(
        [
            mo.md(
                """
                ## 8. Visualize the Result

                The `reduce_dimensions` stage wrote a UMAP embedding into
                `.obsm["X_umap"]`. Each point is a cell; structure here
                is what the deferred clustering tutorial will partition
                with Leiden and annotate with marker genes.
                """
            ),
            fig,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
