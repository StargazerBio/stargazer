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
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
            "env": "test",
        },
        created_at=datetime.now(),
    )

    ref = Reference(
        build="GRCh38",
        fasta=fasta_file,
    )

    # Run bwa_index - it will call ref.fetch() internally
    result = await bwa_index(ref)

    # Verify result
    assert isinstance(result, Reference)
    assert result.build == "GRCh38"

    # Verify all 5 BWA index files were added
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]

    # Collect all index files from aligner_index
    assert len(result.aligner_index) == 5, "Should have exactly 5 BWA index files"

    for ext in index_extensions:
        # Find index file by checking names in aligner_index
        index_files = [
            f for f in result.aligner_index if f and f.name and f.name.endswith(ext)
        ]
        assert len(index_files) == 1, f"Should have exactly one {ext} file"

        index_file = index_files[0]
        assert index_file.size > 0, f"Index file {ext} should not be empty"

        # Verify index file has metadata
        assert index_files[0].keyvalues.get("aligner") == "bwa_index", (
            f"Index file {ext} should have aligner metadata"
        )
        assert index_files[0].keyvalues.get("type") == "reference", (
            f"Index file {ext} should have type metadata"
        )
        assert index_files[0].keyvalues.get("component") == "aligner_index", (
            f"Index file {ext} should have component metadata"
        )
        assert index_files[0].keyvalues.get("build") == "GRCh38", (
            f"Index file {ext} should copy build metadata from reference"
        )
        assert index_file.keyvalues.get("type") == "reference", (
            f"Index file {ext} should have type metadata"
        )
        assert index_file.keyvalues.get("build") == "GRCh38", (
            f"Index file {ext} should copy build metadata from reference"
        )

        # Verify file exists at local_path
        assert index_file.local_path is not None, (
            f"Index file {ext} should have local_path set"
        )
        assert index_file.local_path.exists(), (
            f"Index file {ext} should exist at local_path"
        )

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
            keyvalues={
                "type": "reference",
                "component": "fasta",
                "env": "test",
            },
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
                    keyvalues={
                        "type": "reference",
                        "component": "aligner_index",
                        "aligner": "bwa_index",
                        "env": "test",
                    },
                    created_at=datetime.now(),
                )
            )

    ref = Reference(
        build="GRCh38",
        fasta=files_list[0] if files_list else None,
        aligner_index=files_list[1:] if len(files_list) > 1 else [],
    )

    # Run bwa_index (should not regenerate if all files present)
    result = await bwa_index(ref)

    # Verify result
    assert isinstance(result, Reference)

    # Should still have same number of aligner_index files
    original_index_count = len(files_list) - 1  # Subtract FASTA file
    assert len(result.aligner_index) == original_index_count, (
        "Should not duplicate index files"
    )

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

    # Create a Reference with no FASTA file
    ref = Reference(build="nonexistent.fasta")

    # Should raise ValueError when trying to fetch empty reference
    with pytest.raises(ValueError, match="No files to fetch"):
        await bwa_index(ref)
