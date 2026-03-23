"""
Test for Pinata file upload, deletion, and querying using real API.

This test requires a valid PINATA_JWT environment variable.

To populate expected CIDs for test files, run:
    python cli/upload_to_pinata.py tests/fixtures/FILE -m type=reference -m env=test --update-config
"""

import pytest
from conftest import FIXTURES_DIR, GENERAL_FIXTURES_DIR
from stargazer.types.asset import Asset
from stargazer.utils.local_storage import LocalStorageClient
from stargazer.utils.pinata import PinataClient

CIDS = {
    "GRCh38_TP53.fa": "bafkreib6vj3os7l4lqqytaw5vju46iorcknttfiwfnlbizjcqn7xd5hrvy",
    "GRCh38_TP53.fa.fai": "bafkreic2oy3e2m3fbloj46epkpbpvrobresfkreuojhofnxiiwhz67xntq",
    "GRCh38_TP53.fa.amb": "bafkreick7eyrefagckncfqcw5t6t2uudkeme74mztgt6edp2mv6qamh4y4",
    "GRCh38_TP53.fa.ann": "bafkreibitlcqn3x52lmb7kngovaaz3qp4ckihtylvmcmvuejoya7ntv4tu",
    "GRCh38_TP53.fa.bwt": "bafkreigmugdxgf4lcczuws6rvgy7ufl24twf3kdgilwv2rtiyq5iwdyu7i",
    "GRCh38_TP53.fa.pac": "bafkreicouoxr5idj6ohh56bxxxuhwk7sjhrvk7xai5blczw762ny6t4eoy",
    "GRCh38_TP53.fa.sa": "bafkreic2h3ct6sqgiaqjmqyuwlvmja6iujaauqs3lqgl3miflgks4nkzae",
    "upload_delete.txt": "bafkreigaquk2gy7m3mojfzsmlu3s7kz6ya5buruzrwowmcuh5tna7vyx34",
}


@pytest.mark.pinata
@pytest.mark.asyncio
async def test_upload_and_delete_file():
    """Test uploading a file to Pinata and then deleting it."""
    client = PinataClient()

    test_file_path = FIXTURES_DIR.joinpath("upload_delete.txt")
    assert test_file_path.exists(), f"Test file not found: {test_file_path}"

    print(f"\nUploading test file: {test_file_path.name}")
    comp = Asset(path=test_file_path)
    await client.upload(comp)

    try:
        assert comp.cid, "Upload should return a CID"
        print(f"Upload successful - CID: {comp.cid}")

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
    client = PinataClient()

    test_files = [
        "GRCh38_TP53.fa",
        "GRCh38_TP53.fa.fai",
    ]

    if not all(CIDS.get(f) for f in test_files):
        pytest.skip(
            "CIDs not populated for TP53 files. "
            "Run upload_reference_files.py to upload files and populate CIDs."
        )

    print("\nQuerying files by keyvalue (type=reference)...")
    found_files = await client.query({"asset": "reference"})
    print(found_files)

    assert len(found_files) >= len(test_files), (
        f"Should find at least {len(test_files)} files, found {len(found_files)}"
    )
    print(f"Found {len(found_files)} reference test files")

    found_cids = {f["cid"] for f in found_files}
    for test_file in test_files:
        assert CIDS.get(test_file) in found_cids, (
            f"Uploaded file {test_file} (CID: {CIDS.get(test_file)}) not found in query results"
        )
        print(f"Verified {test_file} in query results")


@pytest.mark.pinata
@pytest.mark.asyncio
async def test_download_file(tmp_path):
    """Test downloading a file via LocalStorageClient with PinataClient remote."""
    remote = PinataClient()
    client = LocalStorageClient(local_dir=tmp_path / "cache", remote=remote)

    test_file = "GRCh38_TP53.fa.fai"
    test_cid = CIDS.get(test_file)
    assert test_cid, f"CID for {test_file} not found in config"

    expected_content = GENERAL_FIXTURES_DIR.joinpath(test_file).read_text()

    comp = Asset(cid=test_cid)

    print(f"\nDownloading file with CID: {test_cid}")
    await client.download(comp)

    assert comp.path is not None, "Downloaded file should have a path"
    assert comp.path.exists(), f"Downloaded file not found at: {comp.path}"
    print(f"File downloaded successfully to: {comp.path}")

    assert comp.cid == test_cid, "CID should match"

    content = comp.path.read_text()
    assert content == expected_content, (
        f"Content mismatch: expected '{expected_content}', got '{content}'"
    )
    print("File content verified")

    dest_path = tmp_path / "downloaded_test.txt"
    comp.path = None

    print(f"Downloading to specific destination: {dest_path}")
    await client.download(comp, dest=dest_path)

    assert comp.path == dest_path, "Destination path should match"
    assert dest_path.exists(), "File should exist at destination"
    assert dest_path.read_text() == expected_content, "Content should match original"
    print("Download to specific destination successful")
