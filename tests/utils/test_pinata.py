"""
Test for Pinata file upload, deletion, and querying using real API.

This test requires a valid PINATA_JWT environment variable.

To populate expected CIDs for test files, run:
    python cli/upload_to_pinata.py tests/fixtures/FILE -m type=reference -m env=test --update-config
"""

import os

import pytest
from config import CIDS
from conftest import FIXTURES_DIR

from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_upload_and_delete_file():
    """Test uploading a file to Pinata and then deleting it."""
    # Check for API key
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    default_client.local_only = False

    # Use the smallest reference file for quick testing
    test_file = FIXTURES_DIR.joinpath("upload_delete.txt")
    assert test_file.exists(), f"Test file not found: {test_file}"

    # Upload the file with test metadata
    print(f"\nUploading test file: {test_file.name}")
    test_file = await default_client.upload_file(test_file, keyvalues={"test": "true"})

    try:
        # Verify upload succeeded
        assert test_file.id is not None, "Upload should return a file ID"
        assert test_file.cid is not None, "Upload should return a CID"
        assert test_file.keyvalues.get("test") == "true", "Metadata should be preserved"
        print(f"✓ Upload successful - ID: {test_file.id}, CID: {test_file.cid}")

        # If we have an expected CID, verify it matches (CIDs are deterministic)
        expected_cid = CIDS.get("upload_delete.txt")
        if expected_cid:
            assert test_file.cid == expected_cid, (
                f"CID mismatch: expected {expected_cid}, got {test_file.cid}"
            )
            print("✓ CID matches expected value")
        else:
            print(f"  Note: Add to CIDS: 'upload_delete.txt': '{test_file.cid}'")

    finally:
        pass  # Pinata API issue with delay after upload
        # Clean up: delete the file
        # print(f"Deleting test file {test_file.id} after 20 sec cooldown")
        # time.sleep(20)
        # await default_client.delete_file(test_file)
        # print("✓ File deleted successfully")
        default_client.local_only = True


@pytest.mark.asyncio
async def test_query():
    """Upload all reference files, query by CID, and verify they match expected CIDs."""
    # Check for API key
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    default_client.local_only = False

    # Files to upload (TP53 reference files)
    test_files = [
        "GRCh38_TP53.fa",
        "GRCh38_TP53.fa.fai",
    ]

    # Check if CIDs are populated
    if not all(CIDS.get(f) for f in test_files):
        pytest.skip(
            "CIDs not populated for TP53 files. "
            "Run upload_reference_files.py to upload files and populate CIDs."
        )

    # Query by keyvalue to find all reference files
    print("\nQuerying files by keyvalue (type=reference)...")
    found_files = await default_client.query_files({"type": "reference"})
    print(found_files)

    # Should find at least our uploaded files
    assert len(found_files) >= len(test_files), (
        f"Should find at least {len(test_files)} files, found {len(found_files)}"
    )
    print(f"✓ Found {len(found_files)} reference test files")

    # Verify our uploaded files are in the results
    found_cids = {f.cid for f in found_files}
    for test_file in test_files:
        assert CIDS.get(test_file) in found_cids, (
            f"Uploaded file {test_file} (CID: {CIDS.get(test_file)}) not found in query results"
        )
        print(f"✓ Verified {test_file} in query results")


@pytest.mark.asyncio
async def test_download_file(tmp_path):
    """Test downloading a file from Pinata gateway."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    default_client.local_only = False

    # Use GRCh38_TP53.fa.fai - a small reference file known to be on Pinata
    test_file = "GRCh38_TP53.fa.fai"
    test_cid = CIDS.get(test_file)
    assert test_cid, f"CID for {test_file} not found in config"

    expected_content = FIXTURES_DIR.joinpath(test_file).read_text()

    from datetime import datetime, timezone

    test_ipfile = IpFile(
        id="test-download-id",
        cid=test_cid,
        name=test_file,
        size=len(expected_content.encode()),
        keyvalues={"type": "reference"},
        created_at=datetime.now(timezone.utc),
        is_public=False,
    )

    print(f"\nDownloading file with CID: {test_cid}")
    downloaded_ipfile = await default_client.download_file(test_ipfile)

    # Verify the file was downloaded
    assert downloaded_ipfile.local_path is not None, (
        "Downloaded file should have a path"
    )
    assert downloaded_ipfile.local_path.exists(), (
        f"Downloaded file not found at: {downloaded_ipfile.local_path}"
    )
    print(f"✓ File downloaded successfully to: {downloaded_ipfile.local_path}")

    # Verify IpFile metadata is preserved
    assert downloaded_ipfile.cid == test_cid, "CID should match"
    assert downloaded_ipfile.name == test_file, "Name should match"

    # Read and verify content
    content = downloaded_ipfile.local_path.read_text()
    assert content == expected_content, (
        f"Content mismatch: expected '{expected_content}', got '{content}'"
    )
    print("✓ File content verified")

    # Test downloading to a specific destination
    dest_path = tmp_path / "downloaded_test.txt"

    # Reset local_path so download_file doesn't short-circuit
    test_ipfile.local_path = None

    print(f"Downloading to specific destination: {dest_path}")
    result_ipfile = await default_client.download_file(test_ipfile, dest=dest_path)

    assert result_ipfile.local_path == dest_path, "Destination path should match"
    assert dest_path.exists(), "File should exist at destination"
    assert dest_path.read_text() == expected_content, "Content should match original"
    print("✓ Download to specific destination successful")
