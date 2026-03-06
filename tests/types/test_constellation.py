"""Tests for Constellation namespace and Constellation.assemble()."""

import pytest
from unittest.mock import AsyncMock, patch

from stargazer.types.asset import Asset
from stargazer.types.constellation import Constellation
from stargazer.types.reference import Reference, ReferenceIndex, AlignerIndex
from stargazer.types.reads import R1, R2


class TestConstellationNamespace:
    def test_single_asset_direct_access(self):
        ref = Reference(
            cid="Qmref", keyvalues={"asset": "reference", "build": "GRCh38"}
        )
        c = Constellation(_assets={"reference": ref})
        assert c.reference is ref

    def test_multiple_assets_returns_list(self):
        idx1 = AlignerIndex(cid="Qm1", keyvalues={"asset": "aligner_index"})
        idx2 = AlignerIndex(cid="Qm2", keyvalues={"asset": "aligner_index"})
        c = Constellation(_assets={"aligner_index": [idx1, idx2]})
        assert isinstance(c.aligner_index, list)
        assert len(c.aligner_index) == 2

    def test_missing_asset_returns_none(self):
        c = Constellation(_assets={})
        assert c.reference is None
        assert c.alignment is None

    def test_different_asset_types_coexist(self):
        ref = Reference(cid="Qmref", keyvalues={"asset": "reference"})
        ridx = ReferenceIndex(cid="Qmidx", keyvalues={"asset": "reference_index"})
        c = Constellation(_assets={"reference": ref, "reference_index": ridx})
        assert c.reference is ref
        assert c.reference_index is ridx

    def test_empty_constellation(self):
        c = Constellation()
        assert c.reference is None

    def test_assets_internal_dict(self):
        ref = Reference(cid="Qmref", keyvalues={"asset": "reference"})
        c = Constellation(_assets={"reference": ref})
        assert "reference" in c._assets


@pytest.mark.asyncio
async def test_assemble_groups_by_asset_key():
    """assemble() groups query results into Constellation by _asset_key."""
    raw_ref = Asset(cid="Qmr", keyvalues={"asset": "reference", "build": "GRCh38"})
    raw_idx = Asset(
        cid="Qmi", keyvalues={"asset": "reference_index", "build": "GRCh38"}
    )

    mock_client = AsyncMock()
    mock_client.query.return_value = [raw_ref, raw_idx]

    with patch("stargazer.utils.storage.default_client", mock_client):
        c = await Constellation.assemble(build="GRCh38")

    assert type(c.reference) is Reference
    assert type(c.reference_index) is ReferenceIndex


@pytest.mark.asyncio
async def test_assemble_list_filter_issues_multiple_queries():
    """asset=["r1", "r2"] generates two queries via cartesian product."""
    r1_raw = Asset(cid="Qmr1", keyvalues={"asset": "r1", "sample_id": "S1"})
    r2_raw = Asset(cid="Qmr2", keyvalues={"asset": "r2", "sample_id": "S1"})

    mock_client = AsyncMock()
    # First call returns r1, second returns r2
    mock_client.query.side_effect = [[r1_raw], [r2_raw]]

    with patch("stargazer.utils.storage.default_client", mock_client):
        c = await Constellation.assemble(sample_id="S1", asset=["r1", "r2"])

    assert mock_client.query.call_count == 2
    assert type(c.r1) is R1
    assert type(c.r2) is R2


@pytest.mark.asyncio
async def test_assemble_deduplicates_by_cid():
    """Duplicate CIDs across multiple queries are deduplicated."""
    raw = Asset(cid="Qmdup", keyvalues={"asset": "reference", "build": "GRCh38"})

    mock_client = AsyncMock()
    mock_client.query.side_effect = [[raw], [raw]]  # same CID returned twice

    with patch("stargazer.utils.storage.default_client", mock_client):
        c = await Constellation.assemble(
            build="GRCh38", asset=["reference", "reference"]
        )

    # Should have exactly one reference, not two
    assert type(c.reference) is Reference


@pytest.mark.asyncio
async def test_assemble_empty_result():
    """assemble() with no matches returns empty Constellation."""
    mock_client = AsyncMock()
    mock_client.query.return_value = []

    with patch("stargazer.utils.storage.default_client", mock_client):
        c = await Constellation.assemble(build="nonexistent")

    assert c.reference is None
    assert c.alignment is None


@pytest.mark.asyncio
async def test_assemble_multiple_same_key_returns_list():
    """Multiple results with same _asset_key become a list."""
    idx1 = Asset(cid="Qm1", keyvalues={"asset": "aligner_index", "aligner": "bwa"})
    idx2 = Asset(cid="Qm2", keyvalues={"asset": "aligner_index", "aligner": "bwa"})

    mock_client = AsyncMock()
    mock_client.query.return_value = [idx1, idx2]

    with patch("stargazer.utils.storage.default_client", mock_client):
        c = await Constellation.assemble(build="GRCh38")

    assert isinstance(c.aligner_index, list)
    assert len(c.aligner_index) == 2
    assert all(type(a) is AlignerIndex for a in c.aligner_index)


@pytest.mark.asyncio
async def test_constellation_fetch():
    """fetch() calls download() on all contained assets."""
    ref = Reference(cid="Qmref", keyvalues={"asset": "reference"})
    ridx = ReferenceIndex(cid="Qmidx", keyvalues={"asset": "reference_index"})
    c = Constellation(_assets={"reference": ref, "reference_index": ridx})

    mock_client = AsyncMock()
    mock_client.local_dir = "/tmp/stargazer"

    with patch("stargazer.utils.storage.default_client", mock_client):
        await c.fetch()

    assert mock_client.download.call_count == 2


@pytest.mark.asyncio
async def test_constellation_fetch_empty_raises():
    """fetch() raises ValueError on empty Constellation."""
    c = Constellation()

    mock_client = AsyncMock()
    with patch("stargazer.utils.storage.default_client", mock_client):
        with pytest.raises(ValueError, match="empty"):
            await c.fetch()


@pytest.mark.asyncio
async def test_constellation_fetch_with_list():
    """fetch() downloads all assets including list assets."""
    idx1 = AlignerIndex(cid="Qm1", keyvalues={"asset": "aligner_index"})
    idx2 = AlignerIndex(cid="Qm2", keyvalues={"asset": "aligner_index"})
    ref = Reference(cid="Qmref", keyvalues={"asset": "reference"})
    c = Constellation(_assets={"reference": ref, "aligner_index": [idx1, idx2]})

    mock_client = AsyncMock()
    mock_client.local_dir = "/tmp/stargazer"

    with patch("stargazer.utils.storage.default_client", mock_client):
        await c.fetch()

    assert mock_client.download.call_count == 3
