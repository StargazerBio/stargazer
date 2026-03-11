"""Tests for assemble() — storage query to specialized asset list."""

import pytest
from unittest.mock import AsyncMock, patch

from stargazer.types.asset import Asset
from stargazer.types.asset import assemble
from stargazer.types.reference import Reference, ReferenceIndex, AlignerIndex
from stargazer.types.reads import R1, R2


@pytest.mark.asyncio
async def test_assemble_returns_specialized_list():
    """assemble() returns a flat list of specialized assets."""
    raw_ref = Asset(cid="Qmr", keyvalues={"asset": "reference", "build": "GRCh38"})
    raw_idx = Asset(
        cid="Qmi", keyvalues={"asset": "reference_index", "build": "GRCh38"}
    )

    mock_client = AsyncMock()
    mock_client.query.return_value = [raw_ref, raw_idx]

    with patch("stargazer.utils.local_storage.default_client", mock_client):
        assets = await assemble(build="GRCh38")

    assert len(assets) == 2
    refs = [a for a in assets if isinstance(a, Reference)]
    idxs = [a for a in assets if isinstance(a, ReferenceIndex)]
    assert len(refs) == 1
    assert len(idxs) == 1


@pytest.mark.asyncio
async def test_assemble_list_filter_issues_multiple_queries():
    """asset=["r1", "r2"] generates two queries via cartesian product."""
    r1_raw = Asset(cid="Qmr1", keyvalues={"asset": "r1", "sample_id": "S1"})
    r2_raw = Asset(cid="Qmr2", keyvalues={"asset": "r2", "sample_id": "S1"})

    mock_client = AsyncMock()
    mock_client.query.side_effect = [[r1_raw], [r2_raw]]

    with patch("stargazer.utils.local_storage.default_client", mock_client):
        assets = await assemble(sample_id="S1", asset=["r1", "r2"])

    assert mock_client.query.call_count == 2
    assert len([a for a in assets if isinstance(a, R1)]) == 1
    assert len([a for a in assets if isinstance(a, R2)]) == 1


@pytest.mark.asyncio
async def test_assemble_deduplicates_by_cid():
    """Duplicate CIDs across multiple queries are deduplicated."""
    raw = Asset(cid="Qmdup", keyvalues={"asset": "reference", "build": "GRCh38"})

    mock_client = AsyncMock()
    mock_client.query.side_effect = [[raw], [raw]]

    with patch("stargazer.utils.local_storage.default_client", mock_client):
        assets = await assemble(build="GRCh38", asset=["reference", "reference"])

    refs = [a for a in assets if isinstance(a, Reference)]
    assert len(refs) == 1


@pytest.mark.asyncio
async def test_assemble_empty_result():
    """assemble() with no matches returns empty list."""
    mock_client = AsyncMock()
    mock_client.query.return_value = []

    with patch("stargazer.utils.local_storage.default_client", mock_client):
        assets = await assemble(build="nonexistent")

    assert assets == []


@pytest.mark.asyncio
async def test_assemble_multiple_same_key():
    """Multiple results with same _asset_key all appear in the list."""
    idx1 = Asset(cid="Qm1", keyvalues={"asset": "aligner_index", "aligner": "bwa"})
    idx2 = Asset(cid="Qm2", keyvalues={"asset": "aligner_index", "aligner": "bwa"})

    mock_client = AsyncMock()
    mock_client.query.return_value = [idx1, idx2]

    with patch("stargazer.utils.local_storage.default_client", mock_client):
        assets = await assemble(build="GRCh38")

    aligner_indices = [a for a in assets if isinstance(a, AlignerIndex)]
    assert len(aligner_indices) == 2
