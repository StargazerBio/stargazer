"""Tests for reduce_dimensions task."""

import scanpy as sc

from stargazer.tasks.scrna.reduce_dimensions import reduce_dimensions


async def test_reduce_dimensions_embeddings(scrna_input):
    """reduce_dimensions adds PCA and UMAP embeddings to .obsm."""
    result = await reduce_dimensions(
        adata=scrna_input("featured.h5ad"), n_pcs=10, n_neighbors=5
    )

    assert result.stage == "reduced"
    ad = sc.read_h5ad(await result.fetch())
    assert "X_pca" in ad.obsm
    assert ad.obsm["X_umap"].shape == (ad.n_obs, 2)
