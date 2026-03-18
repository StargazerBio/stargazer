"""
Unit tests for scRNA-seq tasks.

Each task is tested independently using a small synthetic .h5ad fixture.
Tasks are called directly (bypassing Flyte execution) to verify scanpy
operations produce the expected AnnData structure.
"""

from pathlib import Path

import pytest

FIXTURE_PATH = (
    Path(__file__).parent.parent / "assets" / "scrna" / "synthetic_200x500.h5ad"
)


@pytest.fixture
def raw_adata_asset(fixtures_db):
    """Create an AnnData asset pointing to the synthetic fixture."""
    from stargazer.types.scrna import AnnData

    fixtures_db()
    return AnnData(
        path=FIXTURE_PATH,
        sample_id="test_sample",
        organism="human",
        stage="raw",
        n_obs=200,
        n_vars=500,
    )


@pytest.fixture
def qc_filtered_ad():
    """Load the synthetic fixture and apply QC steps, returning anndata object."""
    import scanpy as sc

    ad = sc.read_h5ad(FIXTURE_PATH)
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
    return ad


@pytest.mark.asyncio
async def test_qc_filter_output_shape(raw_adata_asset, tmp_path):
    """qc_filter reduces obs count and annotates QC metrics."""
    import stargazer.utils.local_storage as _storage
    from stargazer.utils.local_storage import LocalStorageClient
    from stargazer.tasks.scrna.qc_filter import qc_filter

    work_client = LocalStorageClient(local_dir=tmp_path)
    orig = _storage.default_client
    _storage.default_client = work_client
    try:
        result = await qc_filter(
            adata=raw_adata_asset,
            min_genes=1,
            min_cells=1,
            max_pct_mt=80.0,
        )
        assert result.stage == "qc_filtered"
        assert result.n_obs > 0
        assert result.n_vars > 0
        assert result.path is not None
        assert result.path.exists()
        assert result.sample_id == "test_sample"
        assert result.organism == "human"
    finally:
        _storage.default_client = orig


@pytest.mark.asyncio
async def test_normalize_layers(raw_adata_asset, tmp_path):
    """normalize stores raw counts in .layers['counts'] and applies log1p."""
    import scanpy as sc
    import stargazer.utils.local_storage as _storage
    from stargazer.utils.local_storage import LocalStorageClient
    from stargazer.tasks.scrna.qc_filter import qc_filter
    from stargazer.tasks.scrna.normalize import normalize

    work_client = LocalStorageClient(local_dir=tmp_path)
    orig = _storage.default_client
    _storage.default_client = work_client
    try:
        filtered = await qc_filter(
            adata=raw_adata_asset, min_genes=1, min_cells=1, max_pct_mt=80.0
        )
        result = await normalize(adata=filtered)

        assert result.stage == "normalized"
        assert result.path is not None and result.path.exists()

        ad = sc.read_h5ad(result.path)
        assert "counts" in ad.layers
        # log1p values should be >= 0
        assert float(ad.X.min()) >= 0.0
    finally:
        _storage.default_client = orig


@pytest.mark.asyncio
async def test_select_features_hvg(raw_adata_asset, tmp_path):
    """select_features annotates .var with highly_variable column."""
    import scanpy as sc
    import stargazer.utils.local_storage as _storage
    from stargazer.utils.local_storage import LocalStorageClient
    from stargazer.tasks.scrna.qc_filter import qc_filter
    from stargazer.tasks.scrna.normalize import normalize
    from stargazer.tasks.scrna.select_features import select_features

    work_client = LocalStorageClient(local_dir=tmp_path)
    orig = _storage.default_client
    _storage.default_client = work_client
    try:
        filtered = await qc_filter(
            adata=raw_adata_asset, min_genes=1, min_cells=1, max_pct_mt=80.0
        )
        normalized = await normalize(adata=filtered)
        result = await select_features(adata=normalized, n_top_genes=100)

        assert result.stage == "featured"
        ad = sc.read_h5ad(result.path)
        assert "highly_variable" in ad.var.columns
        assert ad.var["highly_variable"].sum() <= 100
    finally:
        _storage.default_client = orig


@pytest.mark.asyncio
async def test_reduce_dimensions_embeddings(raw_adata_asset, tmp_path):
    """reduce_dimensions adds PCA and UMAP embeddings to .obsm."""
    import scanpy as sc
    import stargazer.utils.local_storage as _storage
    from stargazer.utils.local_storage import LocalStorageClient
    from stargazer.tasks.scrna.qc_filter import qc_filter
    from stargazer.tasks.scrna.normalize import normalize
    from stargazer.tasks.scrna.select_features import select_features
    from stargazer.tasks.scrna.reduce_dimensions import reduce_dimensions

    work_client = LocalStorageClient(local_dir=tmp_path)
    orig = _storage.default_client
    _storage.default_client = work_client
    try:
        filtered = await qc_filter(
            adata=raw_adata_asset, min_genes=1, min_cells=1, max_pct_mt=80.0
        )
        normalized = await normalize(adata=filtered)
        featured = await select_features(adata=normalized, n_top_genes=100)
        result = await reduce_dimensions(adata=featured, n_pcs=10, n_neighbors=5)

        assert result.stage == "reduced"
        ad = sc.read_h5ad(result.path)
        assert "X_pca" in ad.obsm
        assert "X_umap" in ad.obsm
        assert ad.obsm["X_umap"].shape == (ad.n_obs, 2)
    finally:
        _storage.default_client = orig


@pytest.mark.asyncio
async def test_cluster_leiden_labels(raw_adata_asset, tmp_path):
    """cluster adds leiden cluster labels to .obs."""
    import scanpy as sc
    import stargazer.utils.local_storage as _storage
    from stargazer.utils.local_storage import LocalStorageClient
    from stargazer.tasks.scrna.qc_filter import qc_filter
    from stargazer.tasks.scrna.normalize import normalize
    from stargazer.tasks.scrna.select_features import select_features
    from stargazer.tasks.scrna.reduce_dimensions import reduce_dimensions
    from stargazer.tasks.scrna.cluster import cluster

    work_client = LocalStorageClient(local_dir=tmp_path)
    orig = _storage.default_client
    _storage.default_client = work_client
    try:
        filtered = await qc_filter(
            adata=raw_adata_asset, min_genes=1, min_cells=1, max_pct_mt=80.0
        )
        normalized = await normalize(adata=filtered)
        featured = await select_features(adata=normalized, n_top_genes=100)
        reduced = await reduce_dimensions(adata=featured, n_pcs=10, n_neighbors=5)
        result = await cluster(adata=reduced, resolution=0.5)

        assert result.stage == "clustered"
        ad = sc.read_h5ad(result.path)
        assert "leiden" in ad.obs.columns
        # At least 1 cluster
        assert ad.obs["leiden"].nunique() >= 1
    finally:
        _storage.default_client = orig


@pytest.mark.asyncio
async def test_find_markers_ranked_genes(raw_adata_asset, tmp_path):
    """find_markers stores ranked genes in .uns."""
    import scanpy as sc
    import stargazer.utils.local_storage as _storage
    from stargazer.utils.local_storage import LocalStorageClient
    from stargazer.tasks.scrna.qc_filter import qc_filter
    from stargazer.tasks.scrna.normalize import normalize
    from stargazer.tasks.scrna.select_features import select_features
    from stargazer.tasks.scrna.reduce_dimensions import reduce_dimensions
    from stargazer.tasks.scrna.cluster import cluster
    from stargazer.tasks.scrna.find_markers import find_markers

    work_client = LocalStorageClient(local_dir=tmp_path)
    orig = _storage.default_client
    _storage.default_client = work_client
    try:
        filtered = await qc_filter(
            adata=raw_adata_asset, min_genes=1, min_cells=1, max_pct_mt=80.0
        )
        normalized = await normalize(adata=filtered)
        featured = await select_features(adata=normalized, n_top_genes=100)
        reduced = await reduce_dimensions(adata=featured, n_pcs=10, n_neighbors=5)
        clustered = await cluster(adata=reduced, resolution=0.5)
        result = await find_markers(adata=clustered)

        assert result.stage == "annotated"
        ad = sc.read_h5ad(result.path)
        assert "rank_genes_groups" in ad.uns
    finally:
        _storage.default_client = orig


class TestScrnaExports:
    """Test that scRNA-seq tasks and types are properly exported."""

    def test_anndata_type_exported(self):
        from stargazer.types import AnnData

        assert AnnData._asset_key == "anndata"

    def test_scrna_tasks_exported(self):
        from stargazer.tasks.scrna import (
            qc_filter,
            normalize,
            select_features,
            reduce_dimensions,
            cluster,
            find_markers,
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
