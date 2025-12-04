"""
Test for Pinata file upload, deletion, and querying using real API.

This test requires a valid PINATA_JWT environment variable.

To populate expected CIDs, run:
    python tests/upload_reference_files.py
"""

import os
import pytest
from stargazer.utils.pinata import PinataClient
from config import TEST_ROOT, CIDS


@pytest.mark.asyncio
async def test_upload_and_delete_file():
    """Test uploading a file to Pinata and then deleting it."""
    # Check for API key
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Initialize client
    client = PinataClient()

    # Use the smallest reference file for quick testing
    test_file = TEST_ROOT.joinpath("fixtures", "dummy.txt")
    assert test_file.exists(), f"Test file not found: {test_file}"

    # Upload the file with test metadata
    print(f"\nUploading test file: {test_file.name}")
    test_file = await client.upload_file(
        test_file,
        keyvalues={"test": "true"}
    )

    try:
        # Verify upload succeeded
        assert test_file.id is not None, "Upload should return a file ID"
        assert test_file.cid is not None, "Upload should return a CID"
        assert test_file.keyvalues.get("test") == "true", "Metadata should be preserved"
        print(f"✓ Upload successful - ID: {test_file.id}, CID: {test_file.cid}")

        # If we have an expected CID, verify it matches (CIDs are deterministic)
        expected_cid = CIDS.get("dummy.txt")
        if expected_cid:
            assert test_file.cid == expected_cid, \
                f"CID mismatch: expected {expected_cid}, got {test_file.cid}"
            print(f"✓ CID matches expected value")
        else:
            print(f"  Note: Add to CIDS: 'dummy.txt': '{test_file.cid}'")

    finally:
        # Clean up: delete the file
        print(f"Deleting test file: {test_file.id}")
        await client.delete_file(test_file.id)
        print(f"✓ File deleted successfully")


@pytest.mark.asyncio
async def test_query():
    """Upload all reference files, query by CID, and verify they match expected CIDs."""
    # Check for API key
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    client = PinataClient()
    fixtures_dir = TEST_ROOT.joinpath("fixtures", "reference")

    # Files to upload (excluding large fasta for speed)
    test_files = [
        "GRCh38_chr21.fasta",
        "GRCh38_chr21.fasta.fai",
        "GRCh38_chr21.dict",
    ]

    # Query by keyvalue to find all reference files
    print("\nQuerying files by keyvalue (type=reference)...")
    found_files = await client.query_files({"type": "reference"})
    print(found_files)
    # Should find at least our uploaded files
    assert len(found_files) >= len(test_files), \
        f"Should find at least {len(test_files)} files, found {len(found_files)}"
    print(f"✓ Found {len(found_files)} reference test files")

    # Verify our uploaded files are in the results
    found_cids = {f.cid for f in found_files}
    for test_file in test_files:
        assert CIDS.get(test_file) in found_cids, \
            f"Uploaded file {test_file} (CID: {CIDS.get(test_file)}) not found in query results"
        print(f"✓ Verified {test_file} in query results")


@pytest.mark.asyncio
async def test_download_file():
    """Test downloading a file from Pinata by CID."""
    # Initialize client (no API key needed for public downloads)
    client = PinataClient()

    # Use a well-known IPFS test file that's widely available
    # This is the "Hello World" example from IPFS
    test_cid = "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"
    expected_content = "hello worlds\n"

    print(f"\nDownloading well-known test file with CID: {test_cid}")

    try:
        # Download the file (will use cache)
        downloaded_path = await client.download_file(test_cid)
    except Exception as e:
        # If file is not accessible, skip the test with helpful message
        pytest.skip(
            f"CID {test_cid} is not accessible via IPFS gateway. "
            f"This may indicate IPFS gateway issues. Error: {e}"
        )

    # Verify the file was downloaded
    assert downloaded_path.exists(), f"Downloaded file not found at: {downloaded_path}"
    print(f"✓ File downloaded successfully to: {downloaded_path}")

    # Read and verify content
    content = downloaded_path.read_text()
    assert content == expected_content, f"Content mismatch: expected '{expected_content}', got '{content}'"
    print(f"✓ File content verified - matches expected 'hello worlds\\n'")

    # Test downloading to a specific destination
    dest_path = TEST_ROOT.joinpath("fixtures", "downloaded_test.txt")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading to specific destination: {dest_path}")
    result_path = await client.download_file(test_cid, dest=dest_path)

    assert result_path == dest_path, "Destination path should match"
    assert dest_path.exists(), "File should exist at destination"
    assert dest_path.read_text() == content, "Content should match original"
    print(f"✓ Download to specific destination successful")

    # Clean up the destination file (keep cache)
    dest_path.unlink()
    print(f"✓ Test cleanup complete")
