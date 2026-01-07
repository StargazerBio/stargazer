"""
Tests for Alignment type.
"""

import shutil
from datetime import datetime

import pytest
from config import TEST_ROOT

from stargazer.types import Alignment
from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_alignment_fetch():
    """Test fetch() downloads BAM and BAI files to cache."""
    # Setup: Pre-populate cache with test BAM files
    bam_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam"
    bai_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam.bai"
    assert bam_fixture.exists(), f"Test fixture not found: {bam_fixture}"
    assert bai_fixture.exists(), f"Test fixture not found: {bai_fixture}"

    # Pre-populate cache using default_client
    test_cid_bam = "QmTestBam"
    test_cid_bai = "QmTestBai"
    default_client.cache_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.cache_dir / test_cid_bam
    cached_bai = default_client.cache_dir / test_cid_bai
    shutil.copy(bam_fixture, cached_bam)
    shutil.copy(bai_fixture, cached_bai)

    # Create IpFile objects for BAM and BAI
    bam_file = IpFile(
        id="test-bam-id",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={
            "type": "alignment",
            "sample_id": "NA12829",
            "file_type": "bam",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
        created_at=datetime.now(),
    )

    bai_file = IpFile(
        id="test-bai-id",
        cid=test_cid_bai,
        name="NA12829_TP53_paired.bam.bai",
        size=cached_bai.stat().st_size,
        keyvalues={"type": "alignment", "sample_id": "NA12829"},
        created_at=datetime.now(),
    )

    # Create Alignment object
    alignment = Alignment(
        sample_id="NA12829",
        bam_name="NA12829_TP53_paired.bam",
        files=[bam_file, bai_file],
    )

    # Run fetch()
    cache_dir = await alignment.fetch()

    # Verify cache directory returned
    assert cache_dir == default_client.cache_dir
    assert cache_dir.exists()

    # Verify both files are in cache (check local_path is set)
    assert bam_file.local_path is not None
    assert bam_file.local_path.exists()
    assert bai_file.local_path is not None
    assert bai_file.local_path.exists()

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()
    if cached_bai.exists():
        cached_bai.unlink()


@pytest.mark.asyncio
async def test_alignment_get_bam_path():
    """Test get_bam_path() returns correct path."""
    # Setup: Pre-populate cache with test BAM
    bam_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam"

    test_cid_bam = "QmTestBamGetPath"
    default_client.cache_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.cache_dir / test_cid_bam
    shutil.copy(bam_fixture, cached_bam)

    # Create IpFile object with local_path set (as if already downloaded)
    bam_file = IpFile(
        id="test-bam-id",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={"type": "alignment", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_bam,
    )

    # Create Alignment object
    alignment = Alignment(
        sample_id="NA12829",
        bam_name="NA12829_TP53_paired.bam",
        files=[bam_file],
    )

    # Test get_bam_path()
    bam_path = alignment.get_bam_path()
    assert bam_path == cached_bam
    assert bam_path.exists()

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()


@pytest.mark.asyncio
async def test_alignment_get_bai_path():
    """Test get_bai_path() returns correct path when present."""
    # Setup: Pre-populate cache with test BAM and BAI
    bam_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam"
    bai_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam.bai"

    test_cid_bam = "QmTestBamGetBai"
    test_cid_bai = "QmTestBaiGetBai"
    default_client.cache_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.cache_dir / test_cid_bam
    cached_bai = default_client.cache_dir / test_cid_bai
    shutil.copy(bam_fixture, cached_bam)
    shutil.copy(bai_fixture, cached_bai)

    # Create IpFile objects with local_path set
    bam_file = IpFile(
        id="test-bam-id",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={"type": "alignment", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_bam,
    )

    bai_file = IpFile(
        id="test-bai-id",
        cid=test_cid_bai,
        name="NA12829_TP53_paired.bam.bai",
        size=cached_bai.stat().st_size,
        keyvalues={"type": "alignment", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_bai,
    )

    # Create Alignment object
    alignment = Alignment(
        sample_id="NA12829",
        bam_name="NA12829_TP53_paired.bam",
        files=[bam_file, bai_file],
    )

    # Test get_bai_path()
    bai_path = alignment.get_bai_path()
    assert bai_path == cached_bai
    assert bai_path.exists()

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()
    if cached_bai.exists():
        cached_bai.unlink()


@pytest.mark.asyncio
async def test_alignment_get_bai_path_none():
    """Test get_bai_path() returns None when BAI not present."""
    # Setup: Pre-populate cache with test BAM only (no BAI)
    bam_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam"

    test_cid_bam = "QmTestBamNoBai"
    default_client.cache_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.cache_dir / test_cid_bam
    shutil.copy(bam_fixture, cached_bam)

    # Create IpFile object with local_path set
    bam_file = IpFile(
        id="test-bam-id",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={"type": "alignment", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_bam,
    )

    # Create Alignment object without BAI
    alignment = Alignment(
        sample_id="NA12829",
        bam_name="NA12829_TP53_paired.bam",
        files=[bam_file],
    )

    # Test get_bai_path() returns None
    bai_path = alignment.get_bai_path()
    assert bai_path is None

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()


@pytest.mark.asyncio
async def test_alignment_add_files():
    """Test add_files() uploads BAM and BAI files with metadata."""
    # Setup: Copy fixtures to use for upload
    bam_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam"
    bai_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_paired.bam.bai"
    assert bam_fixture.exists()
    assert bai_fixture.exists()

    # Create empty Alignment object
    alignment = Alignment(sample_id="NA12829", bam_name="NA12829_TP53_paired.bam")

    # Add files (in local_only mode, this should copy to cache)
    keyvalues = {
        "type": "alignment",
        "sample_id": "NA12829",
        "tool": "fq2bam",
        "file_type": "bam",
        "sorted": "coordinate",
        "duplicates_marked": "true",
    }
    await alignment.add_files(
        file_paths=[bam_fixture, bai_fixture],
        keyvalues=keyvalues,
    )

    # Verify files were added
    assert len(alignment.files) == 2

    # Verify metadata
    assert all(f.keyvalues.get("type") == "alignment" for f in alignment.files)
    assert all(f.keyvalues.get("sample_id") == "NA12829" for f in alignment.files)
    assert all(f.keyvalues.get("tool") == "fq2bam" for f in alignment.files)

    # Cleanup cache (files may have been copied there)
    for f in alignment.files:
        if f.local_path and f.local_path.exists():
            f.local_path.unlink()


@pytest.mark.asyncio
async def test_alignment_add_files_empty_list():
    """Test add_files() raises ValueError for empty list."""
    alignment = Alignment(sample_id="NA12829", bam_name="test.bam")

    with pytest.raises(ValueError, match="No files to add"):
        await alignment.add_files(file_paths=[], keyvalues={})


@pytest.mark.asyncio
async def test_alignment_add_files_missing_file():
    """Test add_files() raises FileNotFoundError for missing files."""
    alignment = Alignment(sample_id="NA12829", bam_name="test.bam")

    with pytest.raises(FileNotFoundError, match="File not found"):
        await alignment.add_files(
            file_paths=[TEST_ROOT / "fixtures" / "nonexistent.bam"],
            keyvalues={"type": "alignment"},
        )


@pytest.mark.asyncio
async def test_alignment_fetch_empty():
    """Test fetch() raises ValueError for empty alignment."""
    alignment = Alignment(sample_id="NA12829", bam_name="test.bam")

    with pytest.raises(ValueError, match="No files to fetch"):
        await alignment.fetch()


@pytest.mark.asyncio
async def test_alignment_get_bam_path_not_found():
    """Test get_bam_path() raises FileNotFoundError when BAM not in files."""
    alignment = Alignment(sample_id="NA12829", bam_name="test.bam", files=[])

    with pytest.raises(FileNotFoundError, match="BAM file test.bam not found"):
        alignment.get_bam_path()


@pytest.mark.asyncio
async def test_alignment_get_bam_path_not_cached():
    """Test get_bam_path() raises error when file not in cache."""
    # Create IpFile without local_path (not fetched yet)
    bam_file = IpFile(
        id="test-bam-id",
        cid="QmTest",
        name="test.bam",
        size=1000,
        keyvalues={"type": "alignment"},
        created_at=datetime.now(),
        local_path=None,  # Not downloaded yet
    )

    alignment = Alignment(sample_id="NA12829", bam_name="test.bam", files=[bam_file])

    with pytest.raises(FileNotFoundError, match="not in cache"):
        alignment.get_bam_path()


@pytest.mark.asyncio
async def test_alignment_metadata_properties():
    """Test Alignment properties read from BAM file keyvalues."""
    # Create BAM file with metadata in keyvalues
    bam_file = IpFile(
        id="test-bam-id",
        cid="QmTest",
        name="test.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "duplicates_marked": "true",
            "sorted": "coordinate",
        },
        created_at=datetime.now(),
    )

    alignment = Alignment(
        sample_id="NA12829",
        bam_name="test.bam",
        files=[bam_file],
    )

    # Properties should read from BAM file keyvalues
    assert alignment.has_duplicates_marked is True
    assert alignment.is_sorted is True

    # Create Alignment with BAM without metadata flags
    bam_file2 = IpFile(
        id="test-bam-id-2",
        cid="QmTest2",
        name="test2.bam",
        size=1000,
        keyvalues={"type": "alignment"},
        created_at=datetime.now(),
    )

    alignment2 = Alignment(sample_id="NA12829", bam_name="test2.bam", files=[bam_file2])

    # Properties should return False when metadata not present
    assert alignment2.has_duplicates_marked is False
    assert alignment2.is_sorted is False
