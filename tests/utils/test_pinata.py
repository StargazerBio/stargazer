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

from stargazer.types.component import ComponentFile
from stargazer.utils.pinata import PinataClient


@pytest.mark.pinata
@pytest.mark.asyncio
async def test_upload_and_delete_file():
    """Test uploading a file to Pinata and then deleting it."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    client = PinataClient()

    # Use the smallest reference file for quick testing
    test_file_path = FIXTURES_DIR.joinpath("upload_delete.txt")
    assert test_file_path.exists(), f"Test file not found: {test_file_path}"

    # Upload the file with test metadata
    print(f"\nUploading test file: {test_file_path.name}")
    comp = ComponentFile(path=test_file_path, keyvalues={"test": "true"})
    await client.upload(comp)

    try:
        # Verify upload succeeded
        assert comp.cid, "Upload should return a CID"
        assert comp.keyvalues.get("test") == "true", "Metadata should be preserved"
        print(f"Upload successful - CID: {comp.cid}")

        # If we have an expected CID, verify it matches (CIDs are deterministic)
        expected_cid = CIDS.get("upload_delete.txt")
        if expected_cid:
            assert comp.cid == expected_cid, (
                f"CID mismatch: expected {expected_cid}, got {comp.cid}"
            )
            print("CID matches expected value")
        else:
            print(f"  Note: Add to CIDS: 'upload_delete.txt': '{comp.cid}'")

    finally:
        pass  # Pinata API issue with delay after upload


@pytest.mark.pinata
@pytest.mark.asyncio
async def test_query():
    """Upload all reference files, query by CID, and verify they match expected CIDs."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    client = PinataClient()

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
    found_files = await client.query({"type": "reference"})
    print(found_files)

    # Should find at least our uploaded files
    assert len(found_files) >= len(test_files), (
        f"Should find at least {len(test_files)} files, found {len(found_files)}"
    )
    print(f"Found {len(found_files)} reference test files")

    # Verify our uploaded files are in the results
    found_cids = {f.cid for f in found_files}
    for test_file in test_files:
        assert CIDS.get(test_file) in found_cids, (
            f"Uploaded file {test_file} (CID: {CIDS.get(test_file)}) not found in query results"
        )
        print(f"Verified {test_file} in query results")


@pytest.mark.pinata
@pytest.mark.asyncio
async def test_download_file(tmp_path):
    """Test downloading a file from Pinata gateway."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    client = PinataClient()

    # Use GRCh38_TP53.fa.fai - a small reference file known to be on Pinata
    test_file = "GRCh38_TP53.fa.fai"
    test_cid = CIDS.get(test_file)
    assert test_cid, f"CID for {test_file} not found in config"

    expected_content = FIXTURES_DIR.joinpath(test_file).read_text()

    comp = ComponentFile(
        cid=test_cid,
        keyvalues={"type": "reference"},
    )

    print(f"\nDownloading file with CID: {test_cid}")
    await client.download(comp)

    # Verify the file was downloaded
    assert comp.path is not None, "Downloaded file should have a path"
    assert comp.path.exists(), f"Downloaded file not found at: {comp.path}"
    print(f"File downloaded successfully to: {comp.path}")

    # Verify ComponentFile metadata is preserved
    assert comp.cid == test_cid, "CID should match"

    # Read and verify content
    content = comp.path.read_text()
    assert content == expected_content, (
        f"Content mismatch: expected '{expected_content}', got '{content}'"
    )
    print("File content verified")

    # Test downloading to a specific destination
    dest_path = tmp_path / "downloaded_test.txt"

    # Reset path so download doesn't short-circuit
    comp.path = None

    print(f"Downloading to specific destination: {dest_path}")
    await client.download(comp, dest=dest_path)

    assert comp.path == dest_path, "Destination path should match"
    assert dest_path.exists(), "File should exist at destination"
    assert dest_path.read_text() == expected_content, "Content should match original"
    print("Download to specific destination successful")
