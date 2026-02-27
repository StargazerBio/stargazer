"""
Tests for Reads type.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.types import Reads
from stargazer.types.reads import R1File, R2File
from stargazer.utils.storage import default_client


@pytest.mark.asyncio
async def test_reads_fetch():
    """Test fetch() downloads all FASTQ files to cache."""
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    r2_fixture = FIXTURES_DIR / "NA12829_TP53_R2.fq.gz"
    assert r1_fixture.exists(), f"Test fixture not found: {r1_fixture}"
    assert r2_fixture.exists(), f"Test fixture not found: {r2_fixture}"

    test_cid_r1 = "QmTestR1"
    test_cid_r2 = "QmTestR2"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_r1 = default_client.local_dir / test_cid_r1
    cached_r2 = default_client.local_dir / test_cid_r2
    shutil.copy(r1_fixture, cached_r1)
    shutil.copy(r2_fixture, cached_r2)

    r1 = R1File(
        cid=test_cid_r1,
        keyvalues={"type": "reads", "component": "r1", "sample_id": "NA12829"},
    )
    r2 = R2File(
        cid=test_cid_r2,
        keyvalues={"type": "reads", "component": "r2", "sample_id": "NA12829"},
    )

    reads = Reads(sample_id="NA12829", r1=r1, r2=r2)

    cache_dir = await reads.fetch()

    assert cache_dir == default_client.local_dir
    assert cache_dir.exists()
    assert reads.r1.path is not None
    assert reads.r1.path.exists()
    assert reads.r2.path is not None
    assert reads.r2.path.exists()


@pytest.mark.asyncio
async def test_reads_get_paths():
    """Test direct access to r1 and r2 components returns correct paths."""
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    r2_fixture = FIXTURES_DIR / "NA12829_TP53_R2.fq.gz"

    test_cid_r1 = "QmTestR1GetPath"
    test_cid_r2 = "QmTestR2GetPath"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_r1 = default_client.local_dir / test_cid_r1
    cached_r2 = default_client.local_dir / test_cid_r2
    shutil.copy(r1_fixture, cached_r1)
    shutil.copy(r2_fixture, cached_r2)

    r1 = R1File(
        cid=test_cid_r1,
        path=cached_r1,
        keyvalues={"type": "reads", "component": "r1", "sample_id": "NA12829"},
    )
    r2 = R2File(
        cid=test_cid_r2,
        path=cached_r2,
        keyvalues={"type": "reads", "component": "r2", "sample_id": "NA12829"},
    )

    reads = Reads(sample_id="NA12829", r1=r1, r2=r2)

    assert reads.r1.path == cached_r1
    assert reads.r1.path.exists()
    assert reads.r2.path == cached_r2
    assert reads.r2.path.exists()


@pytest.mark.asyncio
async def test_reads_get_r2_path_single_end():
    """Test r2 component is None for single-end reads."""
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"

    test_cid_r1 = "QmTestR1SingleEnd"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_r1 = default_client.local_dir / test_cid_r1
    shutil.copy(r1_fixture, cached_r1)

    r1 = R1File(
        cid=test_cid_r1,
        path=cached_r1,
        keyvalues={"type": "reads", "component": "r1", "sample_id": "NA12829"},
    )

    reads = Reads(sample_id="NA12829", r1=r1)

    assert reads.r1.path == cached_r1
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
