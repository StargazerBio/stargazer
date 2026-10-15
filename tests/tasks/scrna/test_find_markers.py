"""Tests for find_markers task."""

import numpy as np
import pytest
import scanpy as sc
from conftest import SCRNA_FIXTURES_DIR

from stargazer.assets.scrna import AnnData
from stargazer.tasks.scrna.find_markers import find_markers

CLUSTERED_FIXTURE = SCRNA_FIXTURES_DIR / "clustered.h5ad"


@pytest.mark.asyncio
async def test_find_markers_ranked_genes(fixtures_db):
    """find_markers stores ranked genes in .uns."""
    adata = AnnData(
        path=CLUSTERED_FIXTURE,
        sample_id="test_sample",
        organism="human",
        stage="clustered",
        n_obs=59,
        n_vars=500,
    )

    fixtures_db()

    result = await find_markers(adata=adata)

    assert result.stage == "annotated"
    ad = sc.read_h5ad(await result.fetch())
    assert "rank_genes_groups" in ad.uns


@pytest.mark.asyncio
async def test_find_markers_tests_log_normalized_data(fixtures_db):
    """Fold changes come from the log-normalized X, which scanpy expects."""
    adata = AnnData(
        path=CLUSTERED_FIXTURE,
        sample_id="test_sample",
        organism="human",
        stage="clustered",
        n_obs=59,
        n_vars=500,
    )

    fixtures_db()

    result = await find_markers(adata=adata)

    got = sc.read_h5ad(await result.fetch()).uns["rank_genes_groups"]
    expected = sc.read_h5ad(CLUSTERED_FIXTURE)
    sc.tl.rank_genes_groups(expected, groupby="leiden", method="wilcoxon")
    want = expected.uns["rank_genes_groups"]
    for group in want["logfoldchanges"].dtype.names:
        np.testing.assert_allclose(
            got["logfoldchanges"][group], want["logfoldchanges"][group], rtol=1e-5
        )


class TestScrnaExports:
    """Test that scRNA-seq tasks and types are properly exported."""

    def test_anndata_type_exported(self):
        """AnnData type is accessible from stargazer.assets."""
        from stargazer.assets import AnnData

        assert AnnData._asset_key == "anndata"

    def test_scrna_tasks_exported(self):
        """All scRNA tasks are importable from stargazer.tasks.scrna."""
        from stargazer.tasks.scrna import (
            cluster,
            find_markers,
            normalize,
            qc_filter,
            reduce_dimensions,
            select_features,
        )

        for task in [
            qc_filter,
            normalize,
            select_features,
            reduce_dimensions,
            cluster,
            find_markers,
        ]:
            assert callable(task)
