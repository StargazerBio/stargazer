"""
Tests for Reads type.
"""

import shutil
from datetime import datetime

import pytest
from conftest import FIXTURES_DIR

from stargazer.types import Reads
from stargazer.utils.storage import default_client
from stargazer.utils.ipfile import IpFile


@pytest.mark.asyncio
async def test_reads_fetch():
    """Test fetch() downloads all FASTQ files to cache."""
    # Setup: Pre-populate cache with test FASTQ files
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    r2_fixture = FIXTURES_DIR / "NA12829_TP53_R2.fq.gz"
    assert r1_fixture.exists(), f"Test fixture not found: {r1_fixture}"
    assert r2_fixture.exists(), f"Test fixture not found: {r2_fixture}"

    # Pre-populate cache using default_client
    test_cid_r1 = "QmTestR1"
    test_cid_r2 = "QmTestR2"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_r1 = default_client.local_dir / test_cid_r1
    cached_r2 = default_client.local_dir / test_cid_r2
    shutil.copy(r1_fixture, cached_r1)
    shutil.copy(r2_fixture, cached_r2)

    # Create IpFile objects for both reads
    r1_file = IpFile(
        id="test-r1-id",
        cid=test_cid_r1,
        name="NA12829_TP53_R1.fq.gz",
        size=cached_r1.stat().st_size,
        keyvalues={
            "type": "reads",
            "component": "r1",
            "sample_id": "NA12829",
            "read_type": "paired",
        },
        created_at=datetime.now(),
    )

    r2_file = IpFile(
        id="test-r2-id",
        cid=test_cid_r2,
        name="NA12829_TP53_R2.fq.gz",
        size=cached_r2.stat().st_size,
        keyvalues={
            "type": "reads",
            "component": "r2",
            "sample_id": "NA12829",
            "read_type": "paired",
        },
        created_at=datetime.now(),
    )

    # Create Reads object with component fields
    reads = Reads(
        sample_id="NA12829",
        r1=r1_file,
        r2=r2_file,
    )

    # Run fetch()
    cache_dir = await reads.fetch()

    # Verify cache directory returned
    assert cache_dir == default_client.local_dir
    assert cache_dir.exists()

    # Verify both files are in cache (check local_path is set)
    assert reads.r1.local_path is not None
    assert reads.r1.local_path.exists()
    assert reads.r2.local_path is not None
    assert reads.r2.local_path.exists()

    # Cleanup
    if cached_r1.exists():
        cached_r1.unlink()
    if cached_r2.exists():
        cached_r2.unlink()


@pytest.mark.asyncio
async def test_reads_get_paths():
    """Test direct access to r1 and r2 components returns correct paths."""
    # Setup: Pre-populate cache with test FASTQ files
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    r2_fixture = FIXTURES_DIR / "NA12829_TP53_R2.fq.gz"

    test_cid_r1 = "QmTestR1GetPath"
    test_cid_r2 = "QmTestR2GetPath"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_r1 = default_client.local_dir / test_cid_r1
    cached_r2 = default_client.local_dir / test_cid_r2
    shutil.copy(r1_fixture, cached_r1)
    shutil.copy(r2_fixture, cached_r2)

    # Create IpFile objects with local_path set (as if already downloaded)
    r1_file = IpFile(
        id="test-r1-id",
        cid=test_cid_r1,
        name="NA12829_TP53_R1.fq.gz",
        size=cached_r1.stat().st_size,
        keyvalues={
            "type": "reads",
            "component": "r1",
            "sample_id": "NA12829",
        },
        created_at=datetime.now(),
        local_path=cached_r1,
    )

    r2_file = IpFile(
        id="test-r2-id",
        cid=test_cid_r2,
        name="NA12829_TP53_R2.fq.gz",
        size=cached_r2.stat().st_size,
        keyvalues={
            "type": "reads",
            "component": "r2",
            "sample_id": "NA12829",
        },
        created_at=datetime.now(),
        local_path=cached_r2,
    )

    # Create Reads object with component fields
    reads = Reads(
        sample_id="NA12829",
        r1=r1_file,
        r2=r2_file,
    )

    # Test direct field access
    r1_path = reads.r1.local_path
    assert r1_path == cached_r1
    assert r1_path.exists()

    # Test direct field access
    r2_path = reads.r2.local_path
    assert r2_path == cached_r2
    assert r2_path.exists()

    # Cleanup
    if cached_r1.exists():
        cached_r1.unlink()
    if cached_r2.exists():
        cached_r2.unlink()


@pytest.mark.asyncio
async def test_reads_get_r2_path_single_end():
    """Test r2 component is None for single-end reads."""
    # Setup: Single-end read
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"

    test_cid_r1 = "QmTestR1SingleEnd"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_r1 = default_client.local_dir / test_cid_r1
    shutil.copy(r1_fixture, cached_r1)

    r1_file = IpFile(
        id="test-r1-id",
        cid=test_cid_r1,
        name="NA12829_TP53_R1.fq.gz",
        size=cached_r1.stat().st_size,
        keyvalues={
            "type": "reads",
            "component": "r1",
            "sample_id": "NA12829",
            "read_type": "single",
        },
        created_at=datetime.now(),
        local_path=cached_r1,
    )

    # Create Reads object with only r1
    reads = Reads(
        sample_id="NA12829",
        r1=r1_file,
    )

    # Test r1 path works
    r1_path = reads.r1.local_path
    assert r1_path == cached_r1

    # Test r2 is None
    assert reads.r2 is None

    # Cleanup
    if cached_r1.exists():
        cached_r1.unlink()


@pytest.mark.asyncio
async def test_reads_update_components():
    """Test update_r1() and update_r2() upload files."""
    # Setup: Copy fixtures to temporary location (will be "uploaded")
    r1_fixture = FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    r2_fixture = FIXTURES_DIR / "NA12829_TP53_R2.fq.gz"
    assert r1_fixture.exists()
    assert r2_fixture.exists()

    # Create empty Reads object
    reads = Reads(sample_id="NA12829")

    # Update r1 component
    r1_ipfile = await reads.update_r1(
        r1_fixture,
        read_type="paired",
        sequencing_platform="ILLUMINA",
    )

    # Update r2 component
    r2_ipfile = await reads.update_r2(
        r2_fixture,
        sequencing_platform="ILLUMINA",
    )

    # Verify r1 component was set
    assert reads.r1 is not None
    assert reads.r1 == r1_ipfile
    assert reads.r1.keyvalues.get("type") == "reads"
    assert reads.r1.keyvalues.get("component") == "r1"
    assert reads.r1.keyvalues.get("sample_id") == "NA12829"
    assert reads.r1.keyvalues.get("sequencing_platform") == "ILLUMINA"

    # Verify r2 component was set
    assert reads.r2 is not None
    assert reads.r2 == r2_ipfile
    assert reads.r2.keyvalues.get("type") == "reads"
    assert reads.r2.keyvalues.get("component") == "r2"
    assert reads.r2.keyvalues.get("sample_id") == "NA12829"
    assert reads.r2.keyvalues.get("sequencing_platform") == "ILLUMINA"

    # Cleanup cache (files may have been copied there)
    if reads.r1.local_path and reads.r1.local_path.exists():
        reads.r1.local_path.unlink()
    if reads.r2.local_path and reads.r2.local_path.exists():
        reads.r2.local_path.unlink()


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
    """Test that local_path is None when file not fetched yet."""
    # Create IpFile without local_path (not fetched yet)
    r1_file = IpFile(
        id="test-r1-id",
        cid="QmTest",
        name="NA12829_TP53_R1.fq.gz",
        size=1000,
        keyvalues={
            "type": "reads",
            "component": "r1",
        },
        created_at=datetime.now(),
        local_path=None,  # Not downloaded yet
    )

    reads = Reads(sample_id="NA12829", r1=r1_file)

    # local_path should be None
    assert reads.r1.local_path is None


@pytest.mark.asyncio
async def test_reads_with_read_group():
    """Test Reads with custom read group metadata."""
    # Create Reads with read group
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
    # Paired-end reads
    r1_file = IpFile(
        id="test-r1-id",
        cid="QmTestR1",
        name="NA12829_TP53_R1.fq.gz",
        size=1000,
        keyvalues={
            "type": "reads",
            "component": "r1",
        },
        created_at=datetime.now(),
    )

    r2_file = IpFile(
        id="test-r2-id",
        cid="QmTestR2",
        name="NA12829_TP53_R2.fq.gz",
        size=1000,
        keyvalues={
            "type": "reads",
            "component": "r2",
        },
        created_at=datetime.now(),
    )

    reads = Reads(sample_id="NA12829", r1=r1_file, r2=r2_file)
    assert reads.is_paired is True

    # Single-end reads
    reads_single = Reads(sample_id="NA12829", r1=r1_file)
    assert reads_single.is_paired is False
