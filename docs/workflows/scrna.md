# scRNA-seq Clustering Pipeline

Single-cell RNA-seq preprocessing and clustering pipeline implemented with
[scanpy](https://scanpy.readthedocs.io/en/stable/) as Flyte v2 tasks.

## Overview

The pipeline follows the standard scanpy clustering tutorial workflow:

```
raw .h5ad → QC filter → normalize → select features → reduce dims → cluster → markers
```

All intermediate results are stored as `AnnData` assets in the Stargazer
object store so each step is independently inspectable and re-runnable.

## Type

### `AnnData` (`src/stargazer/types/scrna.py`)

Asset subclass for `.h5ad` files.

| Field | Type | Description |
|-------|------|-------------|
| `sample_id` | `str` | Sample identifier |
| `n_obs` | `int` | Number of cells/observations |
| `n_vars` | `int` | Number of genes/variables |
| `stage` | `str` | Pipeline stage: `raw`, `qc_filtered`, `normalized`, `featured`, `reduced`, `clustered`, `annotated` |
| `organism` | `str` | Organism (e.g. `human`, `mouse`) |
| `source_cid` | `str` | CID of the input AnnData (provenance) |

## Tasks (`src/stargazer/tasks/scrna/`)

### `qc_filter`
Filters low-quality cells and genes.
- `sc.pp.filter_cells(min_genes=100)` — remove cells with too few genes
- `sc.pp.filter_genes(min_cells=3)` — remove rarely detected genes
- Annotates mitochondrial (`MT-`), ribosomal (`RPS`/`RPL`), and hemoglobin (`HB`) genes
- `sc.pp.calculate_qc_metrics()` — computes per-cell QC stats
- `sc.pp.scrublet()` — doublet detection and removal
- Filters by `pct_counts_mt < max_pct_mt` and `predicted_doublet == False`

### `normalize`
Normalizes counts and applies log transformation.
- `sc.pp.normalize_total()` — library size normalization
- Saves raw counts in `.layers["counts"]` for downstream DE testing
- `sc.pp.log1p()` — log(1+x) transformation

### `select_features`
Selects highly variable genes (HVGs).
- `sc.pp.highly_variable_genes(n_top_genes=2000)` — marks HVG subset in `.var`

### `reduce_dimensions`
Computes PCA, kNN graph, and UMAP.
- `sc.tl.pca(n_comps=50)` → `.obsm["X_pca"]`
- `sc.pp.neighbors(n_neighbors=15)` → `.uns["neighbors"]`
- `sc.tl.umap()` → `.obsm["X_umap"]`

### `cluster`
Assigns cells to communities via Leiden clustering.
- `sc.tl.leiden(flavor="igraph", n_iterations=2, resolution=0.5)` → `.obs["leiden"]`

### `find_markers`
Identifies cluster marker genes by differential expression.
- `sc.tl.rank_genes_groups(method="wilcoxon", layer="counts")` → `.uns["rank_genes_groups"]`

## Workflow (`src/stargazer/workflows/scrna_clustering.py`)

`scrna_clustering_pipeline` assembles a raw AnnData from storage by
`sample_id` and runs the full task chain sequentially.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sample_id` | required | Storage lookup key |
| `organism` | `"human"` | Organism name |
| `n_top_genes` | `2000` | Number of HVGs to select |
| `resolution` | `0.5` | Leiden resolution |
| `max_pct_mt` | `20.0` | Max mitochondrial % |

**Prerequisites:** Upload a raw `.h5ad` with `asset="anndata"` and `stage="raw"` before running.

## Task Environment

`scrna_env` in `src/stargazer/config.py` — 4 CPU, 32Gi memory (scanpy loads full matrices into RAM).
