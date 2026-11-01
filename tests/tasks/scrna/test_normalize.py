"""Tests for normalize task."""

import numpy as np
import scanpy as sc
import scipy.sparse as sp
from conftest import SCRNA_FIXTURES_DIR

from stargazer.tasks.scrna.normalize import normalize


def _dense(matrix):
    """Return a matrix as a dense array, whichever form it was stored in."""
    return matrix.toarray() if sp.issparse(matrix) else matrix


async def test_normalize_layers(scrna_input):
    """normalize keeps the input's raw counts in .layers['counts'] and applies log1p."""
    result = await normalize(adata=scrna_input("qc_filtered.h5ad"))

    assert result.stage == "normalized"
    ad = sc.read_h5ad(await result.fetch())
    raw = sc.read_h5ad(SCRNA_FIXTURES_DIR / "qc_filtered.h5ad")
    np.testing.assert_array_equal(_dense(ad.layers["counts"]), _dense(raw.X))
    assert float(ad.X.min()) >= 0.0
