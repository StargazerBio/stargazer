"""
### Getting Started with Stargazer.

Interactive notebook for exploring the scRNA-seq clustering pipeline.
Load demo data, tune parameters, run tasks step-by-step, and visualize
results at each stage.

spec: [docs/architecture/notebook.md](../../docs/architecture/notebook.md)
"""

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    """Imports and initialization."""
    import warnings

    warnings.filterwarnings("ignore", message="Variable names are not unique")
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="scanpy")

    import marimo as mo
    import flyte
    import matplotlib.pyplot as plt

    flyte.init_from_config()

    mo.md(
        """
        # Stargazer — scRNA-seq Explorer

        Walk through the single-cell clustering pipeline step by step.
        Each section runs a Stargazer task and visualizes the result.
        Adjust parameters with the controls and re-run cells to iterate.
        """
    )
    return flyte, mo, plt


@app.cell
def _(mo):
    """Task and workflow catalog."""
    from stargazer.registry import TaskRegistry

    _registry = TaskRegistry()
    _task_rows = [
        {
            "name": t["name"],
            "description": t["description"],
            "params": ", ".join(f"{p['name']}: {p['type']}" for p in t["params"]),
        }
        for t in _registry.to_catalog()
    ]
    mo.md("## Task Catalog")
    mo.ui.table(_task_rows, label="All registered tasks and workflows", selection=None)
    return


@app.cell
def _(mo):
    """Load demo data from storage."""
    mo.md(
        """
        ## 1. Load Raw Data

        Assemble a raw AnnData from local storage by sample ID.
        If no data is found, fetch the demo bundle first:

        ```python
        from stargazer.utils.local_storage import default_client
        await default_client.fetch_bundle("scrna_demo")
        ```
        """
    )

    sample_id_input = mo.ui.text(value="s1d1", label="Sample ID")
    sample_id_input
    return (sample_id_input,)


@app.cell
async def _(mo, sample_id_input):
    """Assemble raw AnnData from storage."""
    import scanpy as sc
    from stargazer.assets.asset import assemble

    _assets = await assemble(
        sample_id=sample_id_input.value, asset="anndata", stage="raw"
    )
    if not _assets:
        mo.stop(
            True,
            mo.md(
                f"No raw AnnData found for **{sample_id_input.value}**. "
                "Fetch the demo bundle first (see above)."
            ),
        )

    raw_asset = _assets[0]
    await raw_asset.fetch()
    raw_ad = sc.read_h5ad(raw_asset.path)
    raw_ad.var_names_make_unique()

    mo.md(
        f"Loaded **{raw_asset.sample_id}**: "
        f"**{raw_ad.n_obs:,}** cells, **{raw_ad.n_vars:,}** genes"
    )
    return raw_ad, raw_asset, sc


@app.cell
def _(mo, plt, raw_ad, sc):
    """QC metrics on raw data."""
    import numpy as np

    _ad = raw_ad.copy()

    # Annotate gene groups for QC
    _ad.var["mt"] = _ad.var_names.str.startswith("MT-") | _ad.var_names.str.startswith(
        "mt-"
    )
    _ad.var["ribo"] = _ad.var_names.str.startswith(("RPS", "RPL", "Rps", "Rpl"))
    sc.pp.calculate_qc_metrics(_ad, qc_vars=["mt", "ribo"], inplace=True, log1p=False)

    _fig, _axes = plt.subplots(1, 4, figsize=(16, 4))
    _axes[0].hist(_ad.obs["n_genes_by_counts"], bins=50, color="#2196F3")
    _axes[0].set_title("Genes per cell")
    _axes[0].set_xlabel("n_genes")

    _axes[1].hist(_ad.obs["total_counts"], bins=50, color="#4CAF50")
    _axes[1].set_title("Total counts per cell")
    _axes[1].set_xlabel("total_counts")

    _axes[2].hist(_ad.obs["pct_counts_mt"], bins=50, color="#FF5722")
    _axes[2].set_title("% Mitochondrial")
    _axes[2].set_xlabel("pct_counts_mt")

    _axes[3].hist(_ad.obs["pct_counts_ribo"], bins=50, color="#9C27B0")
    _axes[3].set_title("% Ribosomal")
    _axes[3].set_xlabel("pct_counts_ribo")

    _fig.suptitle("Raw QC Metrics", fontsize=14, fontweight="bold")
    _fig.tight_layout()

    mo.md("## 2. Quality Control")
    _fig
    return (np,)


@app.cell
def _(mo):
    """QC parameter controls."""
    min_genes_slider = mo.ui.slider(
        start=50, stop=500, step=25, value=100, label="Min genes per cell"
    )
    min_cells_slider = mo.ui.slider(
        start=1, stop=20, step=1, value=3, label="Min cells per gene"
    )
    max_mt_slider = mo.ui.slider(
        start=5.0, stop=50.0, step=1.0, value=20.0, label="Max % mitochondrial"
    )
    mo.md("### QC Filter Parameters")
    mo.hstack([min_genes_slider, min_cells_slider, max_mt_slider])
    return max_mt_slider, min_cells_slider, min_genes_slider


@app.cell
async def _(max_mt_slider, min_cells_slider, min_genes_slider, mo, raw_asset):
    """Run QC filter task."""
    from stargazer.tasks.scrna import qc_filter

    mo.md("### Running QC filter...")
    filtered_asset = await qc_filter(
        adata=raw_asset,
        min_genes=min_genes_slider.value,
        min_cells=min_cells_slider.value,
        max_pct_mt=max_mt_slider.value,
    )
    mo.md(
        f"After QC: **{filtered_asset.n_obs:,}** cells, "
        f"**{filtered_asset.n_vars:,}** genes "
        f"(removed {raw_asset.n_obs - filtered_asset.n_obs:,} cells)"
    )
    return (filtered_asset,)


@app.cell
async def _(filtered_asset, mo, plt, sc):
    """Post-QC violin plots."""
    await filtered_asset.fetch()
    _ad = sc.read_h5ad(filtered_asset.path)

    _fig, _axes = plt.subplots(1, 3, figsize=(12, 4))

    for _ax, key, color, title in zip(
        _axes,
        ["n_genes_by_counts", "total_counts", "pct_counts_mt"],
        ["#2196F3", "#4CAF50", "#FF5722"],
        ["Genes per cell", "Total counts", "% Mitochondrial"],
    ):
        _vals = _ad.obs[key].values
        _parts = _ax.violinplot(_vals, showmedians=True)
        for _pc in _parts["bodies"]:
            _pc.set_facecolor(color)
            _pc.set_alpha(0.7)
        _ax.set_title(title)
        _ax.set_ylabel(key)
        _ax.set_xticks([])

    _fig.suptitle("Post-QC Distributions", fontsize=14, fontweight="bold")
    _fig.tight_layout()

    mo.md("### Post-QC Distributions")
    _fig
    return


@app.cell
async def _(filtered_asset, mo):
    """Normalize and select features."""
    from stargazer.tasks.scrna import normalize

    mo.md("## 3. Normalize & Feature Selection")
    normalized_asset = await normalize(adata=filtered_asset)
    return (normalized_asset,)


@app.cell
def _(mo):
    """Feature selection parameters."""
    n_genes_slider = mo.ui.slider(
        start=500, stop=5000, step=250, value=2000, label="Top variable genes"
    )
    n_genes_slider
    return (n_genes_slider,)


@app.cell
async def _(mo, n_genes_slider, normalized_asset, plt, sc):
    """Select features and plot HVG dispersion."""
    from stargazer.tasks.scrna import select_features

    featured_asset = await select_features(
        adata=normalized_asset, n_top_genes=n_genes_slider.value
    )
    await featured_asset.fetch()
    _ad = sc.read_h5ad(featured_asset.path)

    _fig, _ax = plt.subplots(figsize=(10, 5))
    _hvg = _ad.var["highly_variable"]
    _ax.scatter(
        _ad.var["means"][~_hvg],
        _ad.var["dispersions_norm"][~_hvg],
        s=1,
        alpha=0.3,
        color="#BDBDBD",
        label="Other",
    )
    _ax.scatter(
        _ad.var["means"][_hvg],
        _ad.var["dispersions_norm"][_hvg],
        s=1,
        alpha=0.5,
        color="#E91E63",
        label=f"HVG (n={_hvg.sum():,})",
    )
    _ax.set_xlabel("Mean expression")
    _ax.set_ylabel("Normalized dispersion")
    _ax.set_title("Highly Variable Genes")
    _ax.legend(markerscale=5)
    _fig.tight_layout()

    mo.md(f"Selected **{_hvg.sum():,}** highly variable genes")
    _fig
    return (featured_asset,)


@app.cell
async def _(featured_asset, mo, plt, sc):
    """Dimensionality reduction: PCA, neighbors, UMAP."""
    from stargazer.tasks.scrna import reduce_dimensions

    mo.md("## 4. Dimensionality Reduction")
    reduced_asset = await reduce_dimensions(adata=featured_asset)
    await reduced_asset.fetch()
    _ad = sc.read_h5ad(reduced_asset.path)

    # Variance explained by PCs
    _fig, _axes = plt.subplots(1, 2, figsize=(14, 5))

    _axes[0].plot(
        range(1, len(_ad.uns["pca"]["variance_ratio"]) + 1),
        _ad.uns["pca"]["variance_ratio"],
        "o-",
        markersize=3,
        color="#3F51B5",
    )
    _axes[0].set_xlabel("Principal Component")
    _axes[0].set_ylabel("Variance Ratio")
    _axes[0].set_title("PCA Scree Plot")

    # UMAP (unclustered)
    _umap = _ad.obsm["X_umap"]
    _axes[1].scatter(_umap[:, 0], _umap[:, 1], s=1, alpha=0.3, color="#607D8B")
    _axes[1].set_xlabel("UMAP1")
    _axes[1].set_ylabel("UMAP2")
    _axes[1].set_title("UMAP (pre-clustering)")
    _axes[1].set_aspect("equal")

    _fig.tight_layout()
    _fig
    return (reduced_asset,)


@app.cell
def _(mo):
    """Clustering parameters."""
    resolution_slider = mo.ui.slider(
        start=0.1, stop=2.0, step=0.1, value=0.5, label="Leiden resolution"
    )
    mo.md("## 5. Clustering")
    resolution_slider
    return (resolution_slider,)


@app.cell
async def _(mo, np, plt, reduced_asset, resolution_slider, sc):
    """Run clustering and plot UMAP with cluster labels."""
    from stargazer.tasks.scrna import cluster

    clustered_asset = await cluster(
        adata=reduced_asset, resolution=resolution_slider.value
    )
    await clustered_asset.fetch()
    clustered_ad = sc.read_h5ad(clustered_asset.path)

    _n_clusters = clustered_ad.obs["leiden"].nunique()

    _fig, _ax = plt.subplots(figsize=(10, 8))
    _umap = clustered_ad.obsm["X_umap"]
    _labels = clustered_ad.obs["leiden"].astype(int)
    _cmap = plt.cm.get_cmap("tab20", _n_clusters)

    _ax.scatter(_umap[:, 0], _umap[:, 1], c=_labels, cmap=_cmap, s=2, alpha=0.6)

    # Label cluster centroids
    for _cl in range(_n_clusters):
        _mask = _labels == _cl
        _cx, _cy = np.median(_umap[_mask, 0]), np.median(_umap[_mask, 1])
        _ax.annotate(
            str(_cl),
            (_cx, _cy),
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8),
        )

    _ax.set_xlabel("UMAP1")
    _ax.set_ylabel("UMAP2")
    _ax.set_title(
        f"Leiden Clustering (resolution={resolution_slider.value}, "
        f"n={_n_clusters} clusters)"
    )
    _ax.set_aspect("equal")
    _fig.tight_layout()

    mo.md(f"Found **{_n_clusters}** clusters")
    _fig
    return clustered_ad, clustered_asset


@app.cell
async def _(clustered_asset, mo, np, plt, sc):
    """Find marker genes and display top markers per cluster."""
    from stargazer.tasks.scrna import find_markers

    mo.md("## 6. Marker Genes")
    annotated_asset = await find_markers(adata=clustered_asset)
    await annotated_asset.fetch()
    annotated_ad = sc.read_h5ad(annotated_asset.path)
    return annotated_ad, annotated_asset


@app.cell
def _(annotated_ad, mo, np, plt):
    """Visualize top marker genes per cluster as a dot plot."""

    _result = annotated_ad.uns["rank_genes_groups"]
    _n_clusters = len(_result["names"][0])
    _n_top = 3

    # Collect top N marker genes per cluster
    _top_genes = []
    for _cl_idx in range(_n_clusters):
        for _rank in range(_n_top):
            _top_genes.append(_result["names"][_rank][_cl_idx])
    _top_genes = list(dict.fromkeys(_top_genes))  # deduplicate, preserve order

    # Build expression matrix: mean expression and fraction expressing per cluster
    _clusters = annotated_ad.obs["leiden"].astype(str)
    _cluster_ids = sorted(_clusters.unique(), key=int)

    # Use raw counts layer if available, else X
    _X = (
        annotated_ad.layers["counts"]
        if "counts" in annotated_ad.layers
        else annotated_ad.X
    )

    _mean_expr = np.zeros((len(_cluster_ids), len(_top_genes)))
    _frac_expr = np.zeros((len(_cluster_ids), len(_top_genes)))

    for _ci, _cl in enumerate(_cluster_ids):
        _mask = (_clusters == _cl).values
        for _gi, _gene in enumerate(_top_genes):
            if _gene in annotated_ad.var_names:
                _gene_idx = list(annotated_ad.var_names).index(_gene)
                _col = _X[_mask, _gene_idx]
                _vals = (
                    np.asarray(_col.todense()).flatten()
                    if hasattr(_col, "todense")
                    else np.asarray(_col).flatten()
                )
                _mean_expr[_ci, _gi] = np.mean(_vals)
                _frac_expr[_ci, _gi] = np.mean(_vals > 0)

    # Dot plot
    _fig, _ax = plt.subplots(
        figsize=(max(12, len(_top_genes) * 0.8), len(_cluster_ids) * 0.5 + 2)
    )

    for _ci in range(len(_cluster_ids)):
        for _gi in range(len(_top_genes)):
            _size = _frac_expr[_ci, _gi] * 200
            _color = _mean_expr[_ci, _gi]
            _ax.scatter(
                _gi,
                _ci,
                s=_size,
                c=_color,
                cmap="Reds",
                vmin=0,
                edgecolors="grey",
                linewidths=0.5,
            )

    _ax.set_xticks(range(len(_top_genes)))
    _ax.set_xticklabels(_top_genes, rotation=90, fontsize=8)
    _ax.set_yticks(range(len(_cluster_ids)))
    _ax.set_yticklabels([f"Cluster {c}" for c in _cluster_ids])
    _ax.set_title(f"Top {_n_top} Marker Genes per Cluster")
    _ax.set_xlabel("Gene")

    # Size legend
    for _frac, _label in [(0.25, "25%"), (0.5, "50%"), (1.0, "100%")]:
        _ax.scatter(
            [], [], s=_frac * 200, c="grey", alpha=0.5, label=f"{_label} expressing"
        )
    _ax.legend(loc="upper right", title="Fraction", framealpha=0.9)

    _fig.tight_layout()

    mo.md(
        f"Top {_n_top} marker genes per cluster (dot size = fraction expressing, color = mean expression)"
    )
    _fig
    return


@app.cell
def _(annotated_ad, mo, np, plt):
    """Cluster composition summary."""
    _clusters = annotated_ad.obs["leiden"].astype(int)
    _counts = _clusters.value_counts().sort_index()

    _fig, _axes = plt.subplots(1, 2, figsize=(14, 5))

    # Bar chart of cluster sizes
    _colors = [plt.cm.tab20(i / max(len(_counts), 1)) for i in range(len(_counts))]
    _axes[0].bar(_counts.index.astype(str), _counts.values, color=_colors)
    _axes[0].set_xlabel("Cluster")
    _axes[0].set_ylabel("Number of cells")
    _axes[0].set_title("Cells per Cluster")

    # Pie chart
    _axes[1].pie(
        _counts.values,
        labels=[str(i) for i in _counts.index],
        colors=_colors,
        autopct="%1.0f%%",
        pctdistance=0.85,
    )
    _axes[1].set_title("Cluster Proportions")

    _fig.tight_layout()
    _fig
    return


@app.cell
def _(annotated_ad, annotated_asset, mo):
    """Pipeline summary."""
    mo.md(
        f"""
        ## Summary

        | Metric | Value |
        |--------|-------|
        | **Sample** | {annotated_asset.sample_id} |
        | **Organism** | {annotated_asset.organism} |
        | **Final cells** | {annotated_ad.n_obs:,} |
        | **Final genes** | {annotated_ad.n_vars:,} |
        | **Clusters** | {annotated_ad.obs["leiden"].nunique()} |
        | **Output CID** | `{annotated_asset.cid}` |

        The annotated AnnData is stored locally and can be loaded
        directly for downstream analysis:

        ```python
        import scanpy as sc
        ad = sc.read_h5ad("{annotated_asset.path}")
        ```
        """
    )
    return


if __name__ == "__main__":
    app.run()
