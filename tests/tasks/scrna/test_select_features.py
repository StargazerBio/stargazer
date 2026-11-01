"""Tests for select_features task."""

import scanpy as sc

from stargazer.tasks.scrna.select_features import select_features


async def test_select_features_hvg(scrna_input):
    """select_features annotates .var with highly_variable column."""
    result = await select_features(
        adata=scrna_input("normalized.h5ad"), n_top_genes=100
    )

    assert result.stage == "featured"
    ad = sc.read_h5ad(await result.fetch())
    assert "highly_variable" in ad.var.columns
    assert ad.var["highly_variable"].sum() <= 100
