"""Script to generate a small synthetic scRNA-seq .h5ad fixture for testing.

Run with: python tests/assets/scrna/generate_fixture.py
"""

from pathlib import Path

import numpy as np


def generate():
    """Generate synthetic pbmc-like AnnData with 200 cells x 500 genes."""
    import anndata as ad

    rng = np.random.default_rng(42)
    n_obs, n_vars = 200, 500

    # Poisson-distributed counts (sparse-like single-cell data)
    X = rng.poisson(1.0, (n_obs, n_vars)).astype(np.float32)

    # Gene names: mix of regular, MT-, RPS/RPL, and HB genes
    gene_names = [f"GENE{i:04d}" for i in range(n_vars)]
    # Sprinkle in QC-relevant genes so filters have something to annotate
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

    out = Path(__file__).parent / "synthetic_200x500.h5ad"
    adata.write_h5ad(out)
    print(f"Written: {out} ({adata.n_obs} cells x {adata.n_vars} genes)")
    return out


if __name__ == "__main__":
    generate()
