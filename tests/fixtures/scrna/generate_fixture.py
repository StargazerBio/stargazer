"""Generate synthetic scRNA-seq .h5ad fixtures for every pipeline stage.

Run with: python tests/fixtures/scrna/generate_fixture.py

Produces one h5ad per stage using the same parameters the tests use:
  raw → qc_filtered → normalized → featured → reduced → clustered

Each test can then load only its input stage fixture, keeping tests isolated.
"""

from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).parent


def _generate_raw():
    """Generate synthetic pbmc-like AnnData with 200 cells x 500 genes."""
    import anndata as ad

    rng = np.random.default_rng(42)
    n_obs, n_vars = 200, 500

    # Poisson-distributed counts (sparse-like single-cell data)
    X = rng.poisson(1.0, (n_obs, n_vars)).astype(np.float32)

    # Gene names: mix of regular, MT-, RPS/RPL, and HB genes
    gene_names = [f"GENE{i:04d}" for i in range(n_vars)]
    for i in range(10):
        gene_names[i] = f"MT-GENE{i:02d}"
    for i in range(10, 20):
        gene_names[i] = f"RPS{i:02d}"
    for i in range(20, 30):
        gene_names[i] = f"RPL{i:02d}"
    for i in range(30, 35):
        gene_names[i] = f"HBA{i:02d}"

    obs_names = [f"CELL{i:04d}" for i in range(n_obs)]

    adata = ad.AnnData(
        X=X,
        obs={"cell_id": obs_names},
        var={"gene_id": gene_names},
    )
    adata.obs_names = obs_names
    adata.var_names = gene_names

    out = OUT_DIR / "synthetic_200x500.h5ad"
    adata.write_h5ad(out)
    print(f"  raw: {out} ({adata.n_obs} x {adata.n_vars})")
    return adata


def _generate_qc_filtered(ad_raw):
    """Apply QC filtering (min_genes=1, min_cells=1, max_pct_mt=80)."""
    import scanpy as sc

    ad = ad_raw.copy()
    sc.pp.filter_cells(ad, min_genes=1)
    sc.pp.filter_genes(ad, min_cells=1)

    ad.var["mt"] = ad.var_names.str.startswith("MT-")
    ad.var["ribo"] = ad.var_names.str.startswith(("RPS", "RPL"))
    ad.var["hb"] = ad.var_names.str.contains("^HB[^(P)]")
    sc.pp.calculate_qc_metrics(
        ad, qc_vars=["mt", "ribo", "hb"], inplace=True, log1p=True
    )
    sc.pp.scrublet(ad)

    ad = ad[ad.obs["pct_counts_mt"] < 80.0]
    ad = ad[~ad.obs["predicted_doublet"]]

    out = OUT_DIR / "qc_filtered.h5ad"
    ad.write_h5ad(out)
    print(f"  qc_filtered: {out} ({ad.n_obs} x {ad.n_vars})")
    return ad


def _generate_normalized(ad_qc):
    """Normalize, store raw counts in layers['counts'], and log1p."""
    import scanpy as sc

    ad = ad_qc.copy()
    sc.pp.normalize_total(ad)
    ad.layers["counts"] = ad.X.copy()
    sc.pp.log1p(ad)

    out = OUT_DIR / "normalized.h5ad"
    ad.write_h5ad(out)
    print(f"  normalized: {out} ({ad.n_obs} x {ad.n_vars})")
    return ad


def _generate_featured(ad_norm):
    """Select top 100 highly variable genes."""
    import scanpy as sc

    ad = ad_norm.copy()
    sc.pp.highly_variable_genes(ad, n_top_genes=100)

    out = OUT_DIR / "featured.h5ad"
    ad.write_h5ad(out)
    print(f"  featured: {out} ({ad.n_obs} x {ad.n_vars})")
    return ad


def _generate_reduced(ad_feat):
    """PCA (10 components), neighbors (k=5), UMAP."""
    import scanpy as sc

    ad = ad_feat.copy()
    sc.tl.pca(ad, n_comps=10)
    sc.pp.neighbors(ad, n_neighbors=5, n_pcs=10)
    sc.tl.umap(ad)

    out = OUT_DIR / "reduced.h5ad"
    ad.write_h5ad(out)
    print(f"  reduced: {out} ({ad.n_obs} x {ad.n_vars})")
    return ad


def _generate_clustered(ad_red):
    """Leiden clustering (resolution=0.5)."""
    import scanpy as sc

    ad = ad_red.copy()
    sc.tl.leiden(
        ad, flavor="igraph", n_iterations=2, resolution=0.5, key_added="leiden"
    )

    out = OUT_DIR / "clustered.h5ad"
    ad.write_h5ad(out)
    print(f"  clustered: {out} ({ad.n_obs} x {ad.n_vars})")
    return ad


def generate():
    """Run the full pipeline and write one fixture per stage."""
    print("Generating scRNA-seq fixtures:")
    ad_raw = _generate_raw()
    ad_qc = _generate_qc_filtered(ad_raw)
    ad_norm = _generate_normalized(ad_qc)
    ad_feat = _generate_featured(ad_norm)
    ad_red = _generate_reduced(ad_feat)
    _generate_clustered(ad_red)
    print("Done.")


if __name__ == "__main__":
    generate()
