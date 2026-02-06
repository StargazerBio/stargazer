"""
Tests for Alignment type.
"""

import shutil
from datetime import datetime

import pytest
from conftest import FIXTURES_DIR

from stargazer.types import Alignment
from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_alignment_fetch():
    """Test fetch() downloads BAM and BAI files to cache."""
    # Setup: Pre-populate cache with test BAM files
    bam_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam"
    bai_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam.bai"
    assert bam_fixture.exists(), f"Test fixture not found: {bam_fixture}"
    assert bai_fixture.exists(), f"Test fixture not found: {bai_fixture}"

    # Pre-populate cache using default_client
    test_cid_bam = "QmTestBam"
    test_cid_bai = "QmTestBai"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.local_dir / test_cid_bam
    cached_bai = default_client.local_dir / test_cid_bai
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
            "component": "alignment",
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
        keyvalues={
            "type": "alignment",
            "component": "index",
            "sample_id": "NA12829",
        },
        created_at=datetime.now(),
    )

    # Create Alignment object with component fields
    alignment = Alignment(
        sample_id="NA12829",
        alignment=bam_file,
        index=bai_file,
    )

    # Run fetch()
    cache_dir = await alignment.fetch()

    # Verify cache directory returned
    assert cache_dir == default_client.local_dir
    assert cache_dir.exists()

    # Verify both files are in cache (check local_path is set)
    assert alignment.alignment.local_path is not None
    assert alignment.alignment.local_path.exists()
    assert alignment.index.local_path is not None
    assert alignment.index.local_path.exists()

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()
    if cached_bai.exists():
        cached_bai.unlink()


@pytest.mark.asyncio
async def test_alignment_get_bam_path():
    """Test direct access to alignment component returns correct path."""
    # Setup: Pre-populate cache with test BAM
    bam_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam"

    test_cid_bam = "QmTestBamGetPath"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.local_dir / test_cid_bam
    shutil.copy(bam_fixture, cached_bam)

    # Create IpFile object with local_path set (as if already downloaded)
    bam_file = IpFile(
        id="test-bam-id",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "NA12829",
        },
        created_at=datetime.now(),
        local_path=cached_bam,
    )

    # Create Alignment object with alignment component
    alignment = Alignment(
        sample_id="NA12829",
        alignment=bam_file,
    )

    # Test direct field access
    bam_path = alignment.alignment.local_path
    assert bam_path == cached_bam
    assert bam_path.exists()

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()


@pytest.mark.asyncio
async def test_alignment_get_bai_path():
    """Test direct access to index component returns correct path when present."""
    # Setup: Pre-populate cache with test BAM and BAI
    bam_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam"
    bai_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam.bai"

    test_cid_bam = "QmTestBamGetBai"
    test_cid_bai = "QmTestBaiGetBai"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.local_dir / test_cid_bam
    cached_bai = default_client.local_dir / test_cid_bai
    shutil.copy(bam_fixture, cached_bam)
    shutil.copy(bai_fixture, cached_bai)

    # Create IpFile objects with local_path set
    bam_file = IpFile(
        id="test-bam-id",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "NA12829",
        },
        created_at=datetime.now(),
        local_path=cached_bam,
    )

    bai_file = IpFile(
        id="test-bai-id",
        cid=test_cid_bai,
        name="NA12829_TP53_paired.bam.bai",
        size=cached_bai.stat().st_size,
        keyvalues={
            "type": "alignment",
            "component": "index",
            "sample_id": "NA12829",
        },
        created_at=datetime.now(),
        local_path=cached_bai,
    )

    # Create Alignment object with both components
    alignment = Alignment(
        sample_id="NA12829",
        alignment=bam_file,
        index=bai_file,
    )

    # Test direct field access
    bai_path = alignment.index.local_path
    assert bai_path == cached_bai
    assert bai_path.exists()

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()
    if cached_bai.exists():
        cached_bai.unlink()


@pytest.mark.asyncio
async def test_alignment_get_bai_path_none():
    """Test index component is None when BAI not present."""
    # Setup: Pre-populate cache with test BAM only (no BAI)
    bam_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam"

    test_cid_bam = "QmTestBamNoBai"
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    cached_bam = default_client.local_dir / test_cid_bam
    shutil.copy(bam_fixture, cached_bam)

    # Create IpFile object with local_path set
    bam_file = IpFile(
        id="test-bam-id",
        cid=test_cid_bam,
        name="NA12829_TP53_paired.bam",
        size=cached_bam.stat().st_size,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "NA12829",
        },
        created_at=datetime.now(),
        local_path=cached_bam,
    )

    # Create Alignment object without index
    alignment = Alignment(
        sample_id="NA12829",
        alignment=bam_file,
    )

    # Test index is None
    assert alignment.index is None

    # Cleanup
    if cached_bam.exists():
        cached_bam.unlink()


@pytest.mark.asyncio
async def test_alignment_update_components():
    """Test update_alignment() and update_index() upload files."""
    # Setup: Copy fixtures to use for upload
    bam_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam"
    bai_fixture = FIXTURES_DIR / "NA12829_TP53_paired.bam.bai"
    assert bam_fixture.exists()
    assert bai_fixture.exists()

    # Create empty Alignment object
    alignment = Alignment(sample_id="NA12829")

    # Update alignment component
    bam_ipfile = await alignment.update_alignment(
        bam_fixture,
        format="bam",
        is_sorted=True,
        duplicates_marked=True,
    )

    # Update index component
    bai_ipfile = await alignment.update_index(bai_fixture)

    # Verify alignment component was set
    assert alignment.alignment is not None
    assert alignment.alignment == bam_ipfile
    assert alignment.alignment.keyvalues.get("type") == "alignment"
    assert alignment.alignment.keyvalues.get("component") == "alignment"
    assert alignment.alignment.keyvalues.get("sample_id") == "NA12829"
    assert alignment.alignment.keyvalues.get("sorted") == "coordinate"
    assert alignment.alignment.keyvalues.get("duplicates_marked") == "true"

    # Verify index component was set
    assert alignment.index is not None
    assert alignment.index == bai_ipfile
    assert alignment.index.keyvalues.get("type") == "alignment"
    assert alignment.index.keyvalues.get("component") == "index"
    assert alignment.index.keyvalues.get("sample_id") == "NA12829"

    # Cleanup cache (files may have been copied there)
    if alignment.alignment.local_path and alignment.alignment.local_path.exists():
        alignment.alignment.local_path.unlink()
    if alignment.index.local_path and alignment.index.local_path.exists():
        alignment.index.local_path.unlink()


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
    """Test that local_path is None when file not fetched yet."""
    # Create IpFile without local_path (not fetched yet)
    bam_file = IpFile(
        id="test-bam-id",
        cid="QmTest",
        name="test.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
        },
        created_at=datetime.now(),
        local_path=None,  # Not downloaded yet
    )

    alignment = Alignment(sample_id="NA12829", alignment=bam_file)

    # local_path should be None
    assert alignment.alignment.local_path is None


@pytest.mark.asyncio
async def test_alignment_metadata_properties():
    """Test Alignment properties read from alignment component keyvalues."""
    # Create BAM file with metadata in keyvalues
    bam_file = IpFile(
        id="test-bam-id",
        cid="QmTest",
        name="test.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "duplicates_marked": "true",
            "sorted": "coordinate",
        },
        created_at=datetime.now(),
    )

    alignment = Alignment(
        sample_id="NA12829",
        alignment=bam_file,
    )

    # Properties should read from alignment keyvalues
    assert alignment.has_duplicates_marked is True
    assert alignment.is_sorted is True

    # Create Alignment with BAM without metadata flags
    bam_file2 = IpFile(
        id="test-bam-id-2",
        cid="QmTest2",
        name="test2.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
        },
        created_at=datetime.now(),
    )

    alignment2 = Alignment(sample_id="NA12829", alignment=bam_file2)

    # Properties should return False when metadata not present
    assert alignment2.has_duplicates_marked is False
    assert alignment2.is_sorted is False


@pytest.mark.asyncio
async def test_alignment_has_bqsr_applied():
    """Test has_bqsr_applied property reads from alignment keyvalues."""
    # Create BAM file with BQSR applied
    bam_file = IpFile(
        id="test-bam-id",
        cid="QmTest",
        name="test.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "bqsr_applied": "true",
        },
        created_at=datetime.now(),
    )

    alignment = Alignment(sample_id="NA12829", alignment=bam_file)

    # Property should return True
    assert alignment.has_bqsr_applied is True

    # Create Alignment without BQSR
    bam_file2 = IpFile(
        id="test-bam-id-2",
        cid="QmTest2",
        name="test2.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
        },
        created_at=datetime.now(),
    )

    alignment2 = Alignment(sample_id="NA12829", alignment=bam_file2)

    # Property should return False
    assert alignment2.has_bqsr_applied is False
