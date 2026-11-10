"""
Tests for the scrna_clustering_pipeline workflow.
"""

import pytest
from conftest import SCRNA_FIXTURES_DIR

from stargazer.assets import assemble
from stargazer.assets.scrna import AnnData
from stargazer.workflows.scrna_clustering import scrna_clustering_pipeline


async def test_pipeline_runs_every_stage_from_a_stored_raw_sample():
    """The pipeline turns a stored raw sample into an annotated result at every stage."""
    import scanpy as sc

    await AnnData.store(
        SCRNA_FIXTURES_DIR / "synthetic_200x500.h5ad",
        sample_id="s1",
        stage="raw",
        organism="human",
    )

    result = await scrna_clustering_pipeline(
        sample_id="s1", n_top_genes=200, max_pct_mt=80.0
    )

    assert result.stage == "annotated"
    assert result.sample_id == "s1"
    assert result.organism == "human"

    ad = sc.read_h5ad(await result.fetch())
    assert "leiden" in ad.obs.columns
    assert "rank_genes_groups" in ad.uns
    assert 0 < ad.n_obs < 200

    stages = {a.stage for a in await assemble(asset="anndata", sample_id="s1")}
    assert stages == {
        "raw",
        "qc_filtered",
        "normalized",
        "featured",
        "reduced",
        "clustered",
        "annotated",
    }


async def test_pipeline_names_a_missing_sample():
    """A sample with no stored raw AnnData is named in the error."""
    with pytest.raises(ValueError, match="No raw AnnData found for sample_id='nope'"):
        await scrna_clustering_pipeline(sample_id="nope")
