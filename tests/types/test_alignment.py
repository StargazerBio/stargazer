"""
Tests for Alignment type.
"""

import pytest
from conftest import FIXTURES_DIR

from stargazer.types import Alignment
from stargazer.types.alignment import AlignmentFile, AlignmentIndex
import stargazer.utils.storage as _storage_mod


@pytest.mark.asyncio
async def test_alignment_fetch(fixtures_db):
    """Test fetch() resolves BAM and BAI paths from CIDs via TinyDB."""
    [bam_r] = await _storage_mod.default_client.query(
        {
            "type": "alignment",
            "component": "alignment",
            "sample_id": "NA12829",
            "stage": "paired",
        }
    )
    [idx_r] = await _storage_mod.default_client.query(
        {
            "type": "alignment",
            "component": "index",
            "sample_id": "NA12829",
            "stage": "paired",
        }
    )

    # No path set — fetch() must resolve via TinyDB
    bam = AlignmentFile(cid=bam_r.cid, keyvalues=bam_r.keyvalues)
    idx = AlignmentIndex(cid=idx_r.cid, keyvalues=idx_r.keyvalues)

    alignment = Alignment(sample_id="NA12829", alignment=bam, index=idx)
    cache_dir = await alignment.fetch()

    assert cache_dir == _storage_mod.default_client.local_dir
    assert cache_dir.exists()
    assert alignment.alignment.path is not None
    assert alignment.alignment.path.exists()
    assert alignment.index.path is not None
    assert alignment.index.path.exists()


@pytest.mark.asyncio
async def test_alignment_get_bam_path():
    """Test direct access to alignment component returns correct path."""
    bam_path = FIXTURES_DIR / "NA12829_TP53_paired.bam"
    assert bam_path.exists()

    bam = AlignmentFile(
        cid="test",
        path=bam_path,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "NA12829",
        },
    )

    alignment = Alignment(sample_id="NA12829", alignment=bam)

    assert alignment.alignment.path == bam_path
    assert alignment.alignment.path.exists()


@pytest.mark.asyncio
async def test_alignment_get_bai_path():
    """Test direct access to index component returns correct path when present."""
    bam_path = FIXTURES_DIR / "NA12829_TP53_paired.bam"
    bai_path = FIXTURES_DIR / "NA12829_TP53_paired.bam.bai"
    assert bam_path.exists()
    assert bai_path.exists()

    bam = AlignmentFile(
        cid="test",
        path=bam_path,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "NA12829",
        },
    )
    idx = AlignmentIndex(
        cid="test",
        path=bai_path,
        keyvalues={"type": "alignment", "component": "index", "sample_id": "NA12829"},
    )

    alignment = Alignment(sample_id="NA12829", alignment=bam, index=idx)

    assert alignment.index.path == bai_path
    assert alignment.index.path.exists()


@pytest.mark.asyncio
async def test_alignment_get_bai_path_none():
    """Test index component is None when BAI not present."""
    bam = AlignmentFile(
        cid="test",
        path=FIXTURES_DIR / "NA12829_TP53_paired.bam",
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "NA12829",
        },
    )

    alignment = Alignment(sample_id="NA12829", alignment=bam)
    assert alignment.index is None


@pytest.mark.asyncio
async def test_alignment_update_components():
    """Test component update() uploads files and sets metadata."""
    bam_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam"
    bai_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam.bai"
    assert bam_fixture.exists()
    assert bai_fixture.exists()

    bam = AlignmentFile()
    await bam.update(
        bam_fixture,
        sample_id="NA12829",
        format="bam",
        sorted="coordinate",
        duplicates_marked=True,
    )

    idx = AlignmentIndex()
    await idx.update(bai_fixture, sample_id="NA12829")

    alignment = Alignment(sample_id="NA12829", alignment=bam, index=idx)

    assert alignment.alignment is not None
    assert alignment.alignment.keyvalues.get("type") == "alignment"
    assert alignment.alignment.keyvalues.get("component") == "alignment"
    assert alignment.alignment.keyvalues.get("sample_id") == "NA12829"
    assert alignment.alignment.keyvalues.get("sorted") == "coordinate"
    assert alignment.alignment.keyvalues.get("duplicates_marked") == "true"
    assert alignment.alignment.cid != ""

    assert alignment.index is not None
    assert alignment.index.keyvalues.get("type") == "alignment"
    assert alignment.index.keyvalues.get("component") == "index"
    assert alignment.index.keyvalues.get("sample_id") == "NA12829"
    assert alignment.index.cid != ""


@pytest.mark.asyncio
async def test_alignment_fetch_empty():
    """Test fetch() raises ValueError for empty alignment."""
    alignment = Alignment(sample_id="NA12829")

    with pytest.raises(ValueError, match="No files to fetch"):
        await alignment.fetch()


@pytest.mark.asyncio
async def test_alignment_get_bam_path_not_found():
    """Test that alignment is None when component not set."""
    alignment = Alignment(sample_id="NA12829")
    assert alignment.alignment is None


@pytest.mark.asyncio
async def test_alignment_get_bam_path_not_cached():
    """Test that path is None when file not fetched yet."""
    bam = AlignmentFile(
        cid="QmTest", keyvalues={"type": "alignment", "component": "alignment"}
    )

    alignment = Alignment(sample_id="NA12829", alignment=bam)
    assert alignment.alignment.path is None


@pytest.mark.asyncio
async def test_alignment_metadata_properties():
    """Test AlignmentFile properties read from keyvalues."""
    bam = AlignmentFile(
        keyvalues={
            "duplicates_marked": "true",
            "sorted": "coordinate",
        }
    )
    alignment = Alignment(sample_id="NA12829", alignment=bam)

    assert alignment.alignment.duplicates_marked is True
    assert alignment.alignment.sorted == "coordinate"

    bam2 = AlignmentFile(keyvalues={})
    alignment2 = Alignment(sample_id="NA12829", alignment=bam2)

    assert alignment2.alignment.duplicates_marked is False
    assert alignment2.alignment.sorted is None


@pytest.mark.asyncio
async def test_alignment_has_bqsr_applied():
    """Test bqsr_applied property reads from keyvalues."""
    bam = AlignmentFile(keyvalues={"bqsr_applied": "true"})
    alignment = Alignment(sample_id="NA12829", alignment=bam)
    assert alignment.alignment.bqsr_applied is True

    bam2 = AlignmentFile(keyvalues={})
    alignment2 = Alignment(sample_id="NA12829", alignment=bam2)
    assert alignment2.alignment.bqsr_applied is False
