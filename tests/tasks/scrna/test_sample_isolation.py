"""Tests that concurrent scRNA task runs for different samples keep separate outputs."""

import asyncio

import pytest

from stargazer.tasks.scrna.cluster import cluster
from stargazer.tasks.scrna.find_markers import find_markers
from stargazer.tasks.scrna.normalize import normalize
from stargazer.tasks.scrna.qc_filter import qc_filter
from stargazer.tasks.scrna.reduce_dimensions import reduce_dimensions
from stargazer.tasks.scrna.select_features import select_features

CASES = [
    (
        qc_filter,
        "synthetic_200x500.h5ad",
        {"min_genes": 1, "min_cells": 1, "max_pct_mt": 80.0},
    ),
    (normalize, "qc_filtered.h5ad", {}),
    (select_features, "normalized.h5ad", {"n_top_genes": 100}),
    (reduce_dimensions, "featured.h5ad", {"n_pcs": 10, "n_neighbors": 5}),
    (cluster, "reduced.h5ad", {"resolution": 0.5}),
    (find_markers, "clustered.h5ad", {}),
]


@pytest.mark.parametrize(
    ("task", "fixture", "kwargs"), CASES, ids=[c[0].name.split(".")[-1] for c in CASES]
)
async def test_parallel_samples_write_distinct_files(
    scrna_input, task, fixture, kwargs
):
    """Two samples run concurrently each get their own output file."""
    inputs = [scrna_input(fixture, sample_id) for sample_id in ("sample_a", "sample_b")]

    a, b = await asyncio.gather(*(task(adata=ad, **kwargs) for ad in inputs))

    assert a.path != b.path
    assert (await a.fetch()).exists()
    assert (await b.fetch()).exists()
