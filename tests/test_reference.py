"""
Tests for Reference type.

Tests cover:
- Hydrating references from Pinata
- Adding files to reference (IPFS and local-only mode)
"""

import os
import tempfile
import pytest
from pathlib import Path
from stargazer.types import Reference
from stargazer.utils.pinata import default_client, PinataClient


@pytest.mark.asyncio
async def test_add_files_empty_list():
    """Test that add_files raises error when file_paths is empty."""
    ref = Reference(ref_name="test.fa")

    with pytest.raises(ValueError, match="No files to add"):
        await ref.add_files(file_paths=[])


@pytest.mark.asyncio
async def test_add_files_nonexistent_file():
    """Test that add_files raises error when file doesn't exist."""
    ref = Reference(ref_name="test.fa")

    with pytest.raises(FileNotFoundError, match="File not found"):
        await ref.add_files(file_paths=[Path("/nonexistent/file.fa")])


@pytest.mark.asyncio
async def test_add_files_success():
    """Test successful file upload to IPFS."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Create temporary test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test files
        test_file1 = tmpdir_path / "test1.txt"
        test_file2 = tmpdir_path / "test2.txt"

        test_file1.write_text("Test content 1")
        test_file2.write_text("Test content 2")

        # Create reference and add files
        ref = Reference(ref_name="test1.txt")

        await ref.add_files(
            file_paths=[test_file1, test_file2],
            keyvalues={"type": "test", "purpose": "unit_test", "env": "test"},
        )

        # Verify files were added to reference
        assert len(ref.files) == 2
        assert all(f.cid for f in ref.files)
        assert all(f.keyvalues.get("type") == "test" for f in ref.files)
        assert all(f.keyvalues.get("purpose") == "unit_test" for f in ref.files)
        assert all(f.keyvalues.get("env") == "test" for f in ref.files)


@pytest.mark.asyncio
async def test_add_files_local_only():
    """Test local-only mode via STARGAZER_LOCAL_ONLY env var."""
    # Save original local_only state
    original_local_only = default_client.local_only

    try:
        # Enable local-only mode on default_client
        default_client.local_only = True
        # Create temporary test files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            test_file1 = tmpdir_path / "local_test1.txt"
            test_file2 = tmpdir_path / "local_test2.txt"

            test_file1.write_text("Local test content 1")
            test_file2.write_text("Local test content 2")

            # Create reference (uses default_client which is now in local_only mode)
            ref = Reference(ref_name="local_test1.txt")

            await ref.add_files(
                file_paths=[test_file1, test_file2],
                keyvalues={"type": "test", "mode": "local", "env": "test"},
            )

            # Verify files were added to reference
            assert len(ref.files) == 2

            # Verify all files have local CIDs
            for f in ref.files:
                assert f.cid.startswith("local_")
                assert f.keyvalues.get("type") == "test"
                assert f.keyvalues.get("mode") == "local"
                assert f.keyvalues.get("env") == "test"

            # Verify files exist in cache
            for f in ref.files:
                cache_path = default_client.local_dir / f.cid
                assert cache_path.exists()
                assert cache_path.is_file()

            # Verify file contents match original
            cache_file1 = default_client.local_dir / ref.files[0].cid
            cache_file2 = default_client.local_dir / ref.files[1].cid

            assert cache_file1.read_text() == "Local test content 1"
            assert cache_file2.read_text() == "Local test content 2"
    finally:
        # Restore original local_only state
        default_client.local_only = original_local_only


@pytest.mark.asyncio
async def test_pinata_client_local_only_env_var():
    """Test that PinataClient respects STARGAZER_LOCAL_ONLY env var."""
    # Test default (not set)
    client = PinataClient()
    assert client.local_only is False

    # Test with env var set to "1"
    os.environ["STARGAZER_LOCAL_ONLY"] = "1"
    client = PinataClient()
    assert client.local_only is True

    # Test with env var set to "true"
    os.environ["STARGAZER_LOCAL_ONLY"] = "true"
    client = PinataClient()
    assert client.local_only is True

    # Test with env var set to "0"
    os.environ["STARGAZER_LOCAL_ONLY"] = "0"
    client = PinataClient()
    assert client.local_only is False

    # Test explicit parameter overrides env var
    os.environ["STARGAZER_LOCAL_ONLY"] = "1"
    client = PinataClient(local_only=False)
    assert client.local_only is False

    # Clean up
    os.environ.pop("STARGAZER_LOCAL_ONLY", None)
