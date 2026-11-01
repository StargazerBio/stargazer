"""Tests for cluster task."""

import scanpy as sc

from stargazer.tasks.scrna.cluster import cluster


async def test_cluster_leiden_labels(scrna_input):
    """cluster adds leiden cluster labels to .obs."""
    result = await cluster(adata=scrna_input("reduced.h5ad"), resolution=0.5)

    assert result.stage == "clustered"
    ad = sc.read_h5ad(await result.fetch())
    assert "leiden" in ad.obs.columns
    assert ad.obs["leiden"].nunique() >= 1
