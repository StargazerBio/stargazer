"""Tests for qc_filter task."""

import anndata
import pytest
import scanpy as sc
from conftest import SCRNA_FIXTURES_DIR

from stargazer.assets.scrna import AnnData
from stargazer.tasks.scrna.qc_filter import qc_filter

RAW_FIXTURE = SCRNA_FIXTURES_DIR / "synthetic_200x500.h5ad"


@pytest.mark.asyncio
async def test_qc_filter_output_shape(fixtures_db):
    """qc_filter reduces obs count and annotates QC metrics."""
    adata = AnnData(
        path=RAW_FIXTURE,
        sample_id="test_sample",
        organism="human",
        stage="raw",
        n_obs=200,
        n_vars=500,
    )

    fixtures_db()

    result = await qc_filter(
        adata=adata,
        min_genes=1,
        min_cells=1,
        max_pct_mt=80.0,
    )

    assert result.stage == "qc_filtered"
    assert result.n_obs > 0
    assert result.n_vars > 0
    assert result.path is not None
    assert (await result.fetch()).exists()
    assert result.sample_id == "test_sample"
    assert result.organism == "human"


def mouse_symbols(name: str) -> str:
    """Rewrite a human-style fixture gene name as a mouse symbol (MT-X -> mt-X)."""
    if name.startswith("MT-"):
        return "mt-" + name[3:].capitalize()
    return name.capitalize()


@pytest.mark.asyncio
async def test_qc_filter_uses_asset_organism_prefixes(fixtures_db, tmp_path):
    """A mouse-labeled asset is filtered on mouse gene prefixes (mt-, Rps/Rpl, Hb)."""
    raw = anndata.read_h5ad(RAW_FIXTURE)
    raw.var_names = [mouse_symbols(n) for n in raw.var_names]
    mouse_path = tmp_path / "mouse_200x500.h5ad"
    raw.write_h5ad(mouse_path)
    adata = AnnData(path=mouse_path, sample_id="mouse_sample", organism="mouse")

    fixtures_db()

    result = await qc_filter(adata=adata, min_genes=1, min_cells=1, max_pct_mt=80.0)

    out = sc.read_h5ad(await result.fetch())
    flagged = {k: int(out.var[k].sum()) for k in ("mt", "ribo", "hb")}
    assert flagged == {"mt": 10, "ribo": 20, "hb": 5}
    assert result.organism == "mouse"


@pytest.mark.asyncio
@pytest.mark.parametrize("organism", ["", "zebrafish"])
async def test_qc_filter_rejects_unsupported_organism(fixtures_db, organism):
    """An asset with no supported organism raises, naming the field and the options."""
    adata = AnnData(path=RAW_FIXTURE, sample_id="test_sample", organism=organism)

    fixtures_db()

    with pytest.raises(ValueError, match=r"organism.*human, mouse"):
        await qc_filter(adata=adata, min_genes=1, min_cells=1, max_pct_mt=80.0)


@pytest.mark.asyncio
async def test_qc_filter_task_is_callable():
    """Test that qc_filter is a callable task."""
    assert callable(qc_filter)
    assert "qc_filter" in str(qc_filter)
