"""
Tests for BWA tasks.
"""

import shutil
from datetime import datetime

import pytest
from config import TEST_ROOT

from stargazer.tasks.general.bwa import bwa_index
from stargazer.types import Reference
from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_bwa_index():
    """Test bwa index creates all index files (.amb, .ann, .bwt, .pac, .sa)."""
    # Check if bwa is available
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

    # Setup: Copy test reference to cache directory
    ref_fixture = TEST_ROOT / "fixtures" / "GRCh38_TP53.fa"
    assert ref_fixture.exists(), f"Test fixture not found: {ref_fixture}"

    # Pre-populate cache using default_client
    test_cid = "QmTestTP53Fasta"
    cached_fasta = default_client.local_dir / test_cid
    default_client.local_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ref_fixture, cached_fasta)

    # Create a Reference with the cached file
    fasta_file = IpFile(
        id="test-id",
        cid=test_cid,
        name="GRCh38_TP53.fa",
        size=cached_fasta.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38", "env": "test"},
        created_at=datetime.now(),
    )

    ref = Reference(
        ref_name="GRCh38_TP53.fa",
        files=[fasta_file],
    )

    # Run bwa_index - it will call ref.fetch() internally
    result = await bwa_index(ref)

    # Verify the result
    assert isinstance(result, Reference)
    assert result.ref_name == "GRCh38_TP53.fa"

    # Verify all 5 BWA index files were added
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for ext in index_extensions:
        index_name = f"GRCh38_TP53.fa{ext}"
        index_files = [f for f in result.files if f.name == index_name]
        assert len(index_files) == 1, f"Should have exactly one {ext} file"
        assert index_files[0].size > 0, f"Index file {ext} should not be empty"

        # Verify the index file has metadata
        assert index_files[0].keyvalues.get("tool") == "bwa_index", (
            f"Index file {ext} should have tool metadata"
        )
        assert index_files[0].keyvalues.get("type") == "reference", (
            f"Index file {ext} should have type metadata"
        )
        assert index_files[0].keyvalues.get("build") == "GRCh38", (
            f"Index file {ext} should copy build metadata from reference"
        )

        # Verify file exists at the local_path
        # BWA creates files with the CID as base name (e.g., QmTestTP53Fasta.amb)
        assert index_files[0].local_path is not None, (
            f"Index file {ext} should have local_path set"
        )
        assert index_files[0].local_path.exists(), (
            f"Index file {ext} should exist at local_path"
        )

    # Total files should be 1 (fasta) + 5 (index files) = 6
    assert len(result.files) == 6

    # Cleanup - use actual cached filenames (CID-based)
    if cached_fasta.exists():
        cached_fasta.unlink()
    for ext in index_extensions:
        # Index files are named with CID as base
        index_path = cached_fasta.parent / f"{test_cid}{ext}"
        if index_path.exists():
            index_path.unlink()


@pytest.mark.asyncio
async def test_bwa_index_idempotent():
    """Test that bwa_index is idempotent (doesn't fail if index files already exist)."""
    # Check if bwa is available
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

    # Setup: Copy test reference to cache directory
    fixtures_ref_dir = TEST_ROOT / "fixtures"

    # Pre-populate cache using default_client
    default_client.local_dir.mkdir(parents=True, exist_ok=True)

    # Create test CIDs for all files
    test_cid_fasta = "QmTestTP53FastaIdempotent"
    cached_fasta = default_client.local_dir / test_cid_fasta
    shutil.copy(fixtures_ref_dir / "GRCh38_TP53.fa", cached_fasta)

    files_list = [
        IpFile(
            id="test-id-fasta",
            cid=test_cid_fasta,
            name="GRCh38_TP53.fa",
            size=cached_fasta.stat().st_size,
            keyvalues={"type": "reference", "env": "test"},
            created_at=datetime.now(),
        )
    ]

    # Add all index files if they exist in fixtures
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    ext_names = ["amb", "ann", "bwt", "pac", "sa"]
    for i, ext in enumerate(index_extensions):
        index_fixture = fixtures_ref_dir / f"GRCh38_TP53.fa{ext}"
        if index_fixture.exists():
            test_cid_index = f"QmTestTP53{ext_names[i].upper()}"
            cached_index = default_client.local_dir / test_cid_index
            shutil.copy(index_fixture, cached_index)

            files_list.append(
                IpFile(
                    id=f"test-id-{ext}",
                    cid=test_cid_index,
                    name=f"GRCh38_TP53.fa{ext}",
                    size=cached_index.stat().st_size,
                    keyvalues={"type": "reference", "env": "test"},
                    created_at=datetime.now(),
                )
            )

    ref = Reference(
        ref_name="GRCh38_TP53.fa",
        files=files_list,
    )

    # Run bwa_index (should not regenerate if all files present)
    result = await bwa_index(ref)

    # Verify the result
    assert isinstance(result, Reference)

    # Should still have same number of files (not duplicates)
    assert len(result.files) == len(files_list), "Should not duplicate index files"

    # Cleanup
    if cached_fasta.exists():
        cached_fasta.unlink()
    for i, ext in enumerate(index_extensions):
        cached_index = default_client.local_dir / f"QmTestTP53{ext_names[i].upper()}"
        if cached_index.exists():
            cached_index.unlink()


@pytest.mark.asyncio
async def test_bwa_index_missing_file():
    """Test that bwa_index raises error when reference file is missing."""
    # Check if bwa is available
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

    # Create a Reference with empty files list
    ref = Reference(
        ref_name="nonexistent.fasta",
        files=[],
    )

    # Should raise ValueError when trying to fetch empty reference
    with pytest.raises(ValueError, match="No files to fetch"):
        await bwa_index(ref)
