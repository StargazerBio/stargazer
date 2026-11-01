"""Tests for find_markers task."""

import numpy as np
import scanpy as sc
from conftest import SCRNA_FIXTURES_DIR

from stargazer.tasks.scrna.find_markers import find_markers


async def test_find_markers_ranks_genes_on_log_normalized_data(scrna_input):
    """Ranked genes land in .uns, with fold changes from the log-normalized X,
    which scanpy expects."""
    result = await find_markers(adata=scrna_input("clustered.h5ad"))

    assert result.stage == "annotated"
    got = sc.read_h5ad(await result.fetch()).uns["rank_genes_groups"]
    expected = sc.read_h5ad(SCRNA_FIXTURES_DIR / "clustered.h5ad")
    sc.tl.rank_genes_groups(expected, groupby="leiden", method="wilcoxon")
    want = expected.uns["rank_genes_groups"]
    for group in want["logfoldchanges"].dtype.names:
        np.testing.assert_allclose(
            got["logfoldchanges"][group], want["logfoldchanges"][group], rtol=1e-5
        )
