"""
Tests for Reads type.
"""

import shutil
from datetime import datetime

import pytest
from config import TEST_ROOT

from stargazer.types import Reads
from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_reads_fetch():
    """Test fetch() downloads all FASTQ files to cache."""
    # Setup: Pre-populate cache with test FASTQ files
    r1_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R1.fq.gz"
    r2_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R2.fq.gz"
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
        keyvalues={"type": "reads", "sample_id": "NA12829", "read_type": "paired"},
        created_at=datetime.now(),
    )

    r2_file = IpFile(
        id="test-r2-id",
        cid=test_cid_r2,
        name="NA12829_TP53_R2.fq.gz",
        size=cached_r2.stat().st_size,
        keyvalues={"type": "reads", "sample_id": "NA12829", "read_type": "paired"},
        created_at=datetime.now(),
    )

    # Create Reads object
    reads = Reads(
        sample_id="NA12829",
        files=[r1_file, r2_file],
        read_group={"ID": "test", "SM": "NA12829"},
    )

    # Run fetch()
    cache_dir = await reads.fetch()

    # Verify cache directory returned
    assert cache_dir == default_client.local_dir
    assert cache_dir.exists()

    # Verify both files are in cache (check local_path is set)
    assert r1_file.local_path.exists()
    assert r2_file.local_path.exists()

    # Cleanup
    if cached_r1.exists():
        cached_r1.unlink()
    if cached_r2.exists():
        cached_r2.unlink()


@pytest.mark.asyncio
async def test_reads_get_paths():
    """Test get_r1_path() and get_r2_path() return correct paths."""
    # Setup: Pre-populate cache with test FASTQ files
    r1_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R1.fq.gz"
    r2_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R2.fq.gz"

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
        keyvalues={"type": "reads", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_r1,
    )

    r2_file = IpFile(
        id="test-r2-id",
        cid=test_cid_r2,
        name="NA12829_TP53_R2.fq.gz",
        size=cached_r2.stat().st_size,
        keyvalues={"type": "reads", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_r2,
    )

    # Create Reads object
    reads = Reads(
        sample_id="NA12829",
        files=[r1_file, r2_file],
    )

    # Test get_r1_path()
    r1_path = reads.get_r1_path()
    assert r1_path == cached_r1
    assert r1_path.exists()

    # Test get_r2_path()
    r2_path = reads.get_r2_path()
    assert r2_path == cached_r2
    assert r2_path.exists()

    # Cleanup
    if cached_r1.exists():
        cached_r1.unlink()
    if cached_r2.exists():
        cached_r2.unlink()


@pytest.mark.asyncio
async def test_reads_get_r2_path_single_end():
    """Test get_r2_path() returns None for single-end reads."""
    # Setup: Single-end read
    r1_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R1.fq.gz"

    test_cid_r1 = "QmTestR1SingleEnd"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_r1 = default_client.local_dir / test_cid_r1
    shutil.copy(r1_fixture, cached_r1)

    r1_file = IpFile(
        id="test-r1-id",
        cid=test_cid_r1,
        name="NA12829_TP53_R1.fq.gz",
        size=cached_r1.stat().st_size,
        keyvalues={"type": "reads", "sample_id": "NA12829", "read_type": "single"},
        created_at=datetime.now(),
        local_path=cached_r1,
    )

    # Create Reads object with only R1
    reads = Reads(
        sample_id="NA12829",
        files=[r1_file],
    )

    # Test get_r1_path() works
    r1_path = reads.get_r1_path()
    assert r1_path == cached_r1

    # Test get_r2_path() returns None
    r2_path = reads.get_r2_path()
    assert r2_path is None

    # Cleanup
    if cached_r1.exists():
        cached_r1.unlink()


@pytest.mark.asyncio
async def test_reads_add_files():
    """Test add_files() uploads FASTQ files with metadata."""
    # Setup: Copy fixtures to temporary location (will be "uploaded")
    r1_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R1.fq.gz"
    r2_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R2.fq.gz"
    assert r1_fixture.exists()
    assert r2_fixture.exists()

    # Create empty Reads object
    reads = Reads(sample_id="NA12829")

    # Add files (in local_only mode, this should copy to cache)
    keyvalues = {
        "type": "reads",
        "sample_id": "NA12829",
        "read_type": "paired",
    }
    await reads.add_files(
        file_paths=[r1_fixture, r2_fixture],
        keyvalues=keyvalues,
    )

    # Verify files were added
    assert len(reads.files) == 2

    # Verify metadata
    assert all(f.keyvalues.get("type") == "reads" for f in reads.files)
    assert all(f.keyvalues.get("sample_id") == "NA12829" for f in reads.files)
    assert all(f.keyvalues.get("read_type") == "paired" for f in reads.files)

    # Cleanup cache (files may have been copied there)
    for f in reads.files:
        if f.local_path and f.local_path.exists():
            f.local_path.unlink()


@pytest.mark.asyncio
async def test_reads_add_files_empty_list():
    """Test add_files() raises ValueError for empty list."""
    reads = Reads(sample_id="NA12829")

    with pytest.raises(ValueError, match="No files to add"):
        await reads.add_files(file_paths=[], keyvalues={})


@pytest.mark.asyncio
async def test_reads_add_files_missing_file():
    """Test add_files() raises FileNotFoundError for missing files."""
    reads = Reads(sample_id="NA12829")

    with pytest.raises(FileNotFoundError, match="File not found"):
        await reads.add_files(
            file_paths=[TEST_ROOT / "fixtures" / "nonexistent.fq.gz"],
            keyvalues={"type": "reads"},
        )


@pytest.mark.asyncio
async def test_reads_fetch_empty():
    """Test fetch() raises ValueError for empty reads."""
    reads = Reads(sample_id="NA12829")

    with pytest.raises(ValueError, match="No files to fetch"):
        await reads.fetch()


@pytest.mark.asyncio
async def test_reads_get_r1_path_not_found():
    """Test get_r1_path() raises FileNotFoundError when R1 not in files."""
    reads = Reads(sample_id="NA12829", files=[])

    with pytest.raises(FileNotFoundError, match="R1 file not found"):
        reads.get_r1_path()


@pytest.mark.asyncio
async def test_reads_get_r1_path_not_cached():
    """Test get_r1_path() raises error when file not in cache."""
    # Create IpFile without local_path (not fetched yet)
    r1_file = IpFile(
        id="test-r1-id",
        cid="QmTest",
        name="NA12829_TP53_R1.fq.gz",
        size=1000,
        keyvalues={"type": "reads"},
        created_at=datetime.now(),
        local_path=None,  # Not downloaded yet
    )

    reads = Reads(sample_id="NA12829", files=[r1_file])

    with pytest.raises(FileNotFoundError, match="not in cache"):
        reads.get_r1_path()


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
