"""
Tests for Reads type.
"""

import pytest
from conftest import FIXTURES_DIR

from stargazer.types import Reads
from stargazer.types.reads import R1File, R2File
import stargazer.utils.storage as _storage_mod


@pytest.mark.asyncio
async def test_reads_fetch(fixtures_db):
    """Test fetch() resolves R1 and R2 paths from CIDs via TinyDB."""
    [r1_r] = await _storage_mod.default_client.query(
        {"type": "reads", "component": "r1", "sample_id": "NA12829"}
    )
    [r2_r] = await _storage_mod.default_client.query(
        {"type": "reads", "component": "r2", "sample_id": "NA12829"}
    )

    # No path set — fetch() must resolve via TinyDB
    r1 = R1File(cid=r1_r.cid, keyvalues=r1_r.keyvalues)
    r2 = R2File(cid=r2_r.cid, keyvalues=r2_r.keyvalues)

    reads = Reads(sample_id="NA12829", r1=r1, r2=r2)
    cache_dir = await reads.fetch()

    assert cache_dir == _storage_mod.default_client.local_dir
    assert cache_dir.exists()
    assert reads.r1.path is not None
    assert reads.r1.path.exists()
    assert reads.r2.path is not None
    assert reads.r2.path.exists()


@pytest.mark.asyncio
async def test_reads_get_paths():
    """Test direct access to r1 and r2 components returns correct paths."""
    r1_path = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    r2_path = FIXTURES_DIR / "NA12829_TP53_R2.fq.gz"
    assert r1_path.exists()
    assert r2_path.exists()

    r1 = R1File(
        cid="test",
        path=r1_path,
        keyvalues={"type": "reads", "component": "r1", "sample_id": "NA12829"},
    )
    r2 = R2File(
        cid="test",
        path=r2_path,
        keyvalues={"type": "reads", "component": "r2", "sample_id": "NA12829"},
    )

    reads = Reads(sample_id="NA12829", r1=r1, r2=r2)

    assert reads.r1.path == r1_path
    assert reads.r1.path.exists()
    assert reads.r2.path == r2_path
    assert reads.r2.path.exists()


@pytest.mark.asyncio
async def test_reads_get_r2_path_single_end():
    """Test r2 component is None for single-end reads."""
    r1_path = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    assert r1_path.exists()

    r1 = R1File(
        cid="test",
        path=r1_path,
        keyvalues={"type": "reads", "component": "r1", "sample_id": "NA12829"},
    )

    reads = Reads(sample_id="NA12829", r1=r1)

    assert reads.r1.path == r1_path
    assert reads.r2 is None


@pytest.mark.asyncio
async def test_reads_update_components():
    """Test component update() uploads files and sets metadata."""
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    r2_fixture = FIXTURES_DIR / "NA12829_TP53_R2.fq.gz"
    assert r1_fixture.exists()
    assert r2_fixture.exists()

    r1 = R1File()
    await r1.update(r1_fixture, sample_id="NA12829", sequencing_platform="ILLUMINA")

    r2 = R2File()
    await r2.update(r2_fixture, sample_id="NA12829", sequencing_platform="ILLUMINA")

    reads = Reads(sample_id="NA12829", r1=r1, r2=r2)

    assert reads.r1 is not None
    assert reads.r1.keyvalues.get("type") == "reads"
    assert reads.r1.keyvalues.get("component") == "r1"
    assert reads.r1.keyvalues.get("sample_id") == "NA12829"
    assert reads.r1.keyvalues.get("sequencing_platform") == "ILLUMINA"
    assert reads.r1.cid != ""

    assert reads.r2 is not None
    assert reads.r2.keyvalues.get("type") == "reads"
    assert reads.r2.keyvalues.get("component") == "r2"
    assert reads.r2.keyvalues.get("sample_id") == "NA12829"
    assert reads.r2.keyvalues.get("sequencing_platform") == "ILLUMINA"
    assert reads.r2.cid != ""


@pytest.mark.asyncio
async def test_reads_fetch_empty():
    """Test fetch() raises ValueError for empty reads."""
    reads = Reads(sample_id="NA12829")

    with pytest.raises(ValueError, match="No files to fetch"):
        await reads.fetch()


@pytest.mark.asyncio
async def test_reads_get_r1_path_not_found():
    """Test that r1 is None when component not set."""
    reads = Reads(sample_id="NA12829")
    assert reads.r1 is None


@pytest.mark.asyncio
async def test_reads_get_r1_path_not_cached():
    """Test that path is None when file not fetched yet."""
    r1 = R1File(cid="QmTest", keyvalues={"type": "reads", "component": "r1"})
    reads = Reads(sample_id="NA12829", r1=r1)
    assert reads.r1.path is None


@pytest.mark.asyncio
async def test_reads_with_read_group():
    """Test Reads with custom read group metadata."""
    reads = Reads(
        sample_id="NA12829",
        read_group={
            "ID": "test_rg",
            "SM": "NA12829",
            "LB": "library1",
            "PL": "ILLUMINA",
            "PU": "unit1",
        },
    )

    assert reads.read_group["ID"] == "test_rg"
    assert reads.read_group["SM"] == "NA12829"
    assert reads.read_group["LB"] == "library1"
    assert reads.read_group["PL"] == "ILLUMINA"
    assert reads.read_group["PU"] == "unit1"


@pytest.mark.asyncio
async def test_reads_is_paired():
    """Test is_paired property."""
    r1 = R1File(keyvalues={"type": "reads", "component": "r1"})
    r2 = R2File(keyvalues={"type": "reads", "component": "r2"})

    reads = Reads(sample_id="NA12829", r1=r1, r2=r2)
    assert reads.is_paired is True

    reads_single = Reads(sample_id="NA12829", r1=r1)
    assert reads_single.is_paired is False
