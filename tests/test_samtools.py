"""
Tests for samtools and bwa tasks.
"""

import shutil
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

from stargazer.types import Reference
from stargazer.tasks.samtools import samtools_faidx, bwa_index
from stargazer.utils.pinata import IpFile, PinataClient
from config import TEST_ROOT


@pytest.mark.asyncio
async def test_samtools_faidx():
    """Test samtools faidx creates .fai index file."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Copy test reference to cache directory
    ref_fixture = TEST_ROOT / "fixtures" / "reference" / "GRCh38_chr21.fasta"
    assert ref_fixture.exists(), f"Test fixture not found: {ref_fixture}"

    # Create a PinataClient and pre-populate cache
    client = PinataClient()
    test_cid = "QmTestFasta123"
    cached_fasta = client.cache_dir / test_cid
    client.cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ref_fixture, cached_fasta)

    # Create a Reference with the cached file
    fasta_file = IpFile(
        id="test-id",
        cid=test_cid,
        name="GRCh38_chr21.fasta",
        size=cached_fasta.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38"},
        created_at=datetime.now(),
    )

    ref = Reference(
        ref_name="GRCh38_chr21.fasta",
        files=[fasta_file],
        client=client,
    )

    # Run samtools_faidx - it will call ref.fetch() internally
    result = await samtools_faidx(ref)

    # Verify the result
    assert isinstance(result, Reference)
    assert result.ref_name == "GRCh38_chr21.fasta"

    # Verify .fai file was added to files list
    fai_files = [f for f in result.files if f.name == "GRCh38_chr21.fasta.fai"]
    assert len(fai_files) == 1, "Should have exactly one .fai file"
    assert fai_files[0].size > 0, "Index file should not be empty"

    # Verify .fai file exists in cache directory
    fai_path = cached_fasta.parent / "GRCh38_chr21.fasta.fai"
    assert fai_path.exists(), "Index file should be in cache directory"

    # Cleanup
    if cached_fasta.exists():
        cached_fasta.unlink()
    if fai_path.exists():
        fai_path.unlink()


@pytest.mark.asyncio
async def test_samtools_faidx_idempotent():
    """Test that samtools_faidx is idempotent (doesn't fail if .fai already exists)."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Copy test reference to cache directory
    fixtures_ref_dir = TEST_ROOT / "fixtures" / "reference"

    # Create a PinataClient and pre-populate cache
    client = PinataClient()
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    test_cid_fasta = "QmTestFasta456"
    test_cid_fai = "QmTestFai456"
    cached_fasta = client.cache_dir / test_cid_fasta
    cached_fai = client.cache_dir / test_cid_fai
    shutil.copy(fixtures_ref_dir / "GRCh38_chr21.fasta", cached_fasta)
    shutil.copy(fixtures_ref_dir / "GRCh38_chr21.fasta.fai", cached_fai)

    # Create Reference with both files already present
    fasta_file = IpFile(
        id="test-id-fasta",
        cid=test_cid_fasta,
        name="GRCh38_chr21.fasta",
        size=cached_fasta.stat().st_size,
        keyvalues={"type": "reference"},
        created_at=datetime.now(),
    )

    fai_file = IpFile(
        id="test-id-fai",
        cid=test_cid_fai,
        name="GRCh38_chr21.fasta.fai",
        size=cached_fai.stat().st_size,
        keyvalues={"type": "reference"},
        created_at=datetime.now(),
    )

    ref = Reference(
        ref_name="GRCh38_chr21.fasta",
        files=[fasta_file, fai_file],
        client=client,
    )

    # Run samtools_faidx (should not regenerate)
    result = await samtools_faidx(ref)

    # Verify the result
    assert isinstance(result, Reference)

    # Should still have exactly 2 files (not 3)
    assert len(result.files) == 2, "Should not duplicate .fai file"

    # Verify .fai file exists
    fai_files = [f for f in result.files if f.name == "GRCh38_chr21.fasta.fai"]
    assert len(fai_files) == 1, "Should have exactly one .fai file"

    # Cleanup
    if cached_fasta.exists():
        cached_fasta.unlink()
    if cached_fai.exists():
        cached_fai.unlink()


@pytest.mark.asyncio
async def test_samtools_faidx_missing_file():
    """Test that samtools_faidx raises error when reference file is missing."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Create a Reference with empty files list
    ref = Reference(
        ref_name="nonexistent.fasta",
        files=[],
    )

    # Should raise ValueError when trying to fetch empty reference
    with pytest.raises(ValueError, match="No files to fetch"):
        await samtools_faidx(ref)


@pytest.mark.asyncio
async def test_bwa_index():
    """Test bwa index creates all index files (.amb, .ann, .bwt, .pac, .sa)."""
    # Check if bwa is available
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

    # Setup: Copy test reference to cache directory
    ref_fixture = TEST_ROOT / "fixtures" / "reference" / "GRCh38_chr21.fasta"
    assert ref_fixture.exists(), f"Test fixture not found: {ref_fixture}"

    # Create a PinataClient and pre-populate cache
    client = PinataClient()
    test_cid = "QmTestBwaFasta123"
    cached_fasta = client.cache_dir / test_cid
    client.cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ref_fixture, cached_fasta)

    # Create a Reference with the cached file
    fasta_file = IpFile(
        id="test-id",
        cid=test_cid,
        name="GRCh38_chr21.fasta",
        size=cached_fasta.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38"},
        created_at=datetime.now(),
    )

    ref = Reference(
        ref_name="GRCh38_chr21.fasta",
        files=[fasta_file],
        client=client,
    )

    # Run bwa_index - it will call ref.fetch() internally
    result = await bwa_index(ref)

    # Verify the result
    assert isinstance(result, Reference)
    assert result.ref_name == "GRCh38_chr21.fasta"

    # Verify all 5 BWA index files were added
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for ext in index_extensions:
        index_name = f"GRCh38_chr21.fasta{ext}"
        index_files = [f for f in result.files if f.name == index_name]
        assert len(index_files) == 1, f"Should have exactly one {ext} file"
        assert index_files[0].size > 0, f"Index file {ext} should not be empty"

        # Verify file exists in cache directory
        index_path = cached_fasta.parent / index_name
        assert index_path.exists(), f"Index file {ext} should be in cache directory"

    # Total files should be 1 (fasta) + 5 (index files) = 6
    assert len(result.files) == 6

    # Cleanup
    if cached_fasta.exists():
        cached_fasta.unlink()
    for ext in index_extensions:
        index_path = cached_fasta.parent / f"GRCh38_chr21.fasta{ext}"
        if index_path.exists():
            index_path.unlink()


@pytest.mark.asyncio
async def test_bwa_index_idempotent():
    """Test that bwa_index is idempotent (doesn't fail if index files already exist)."""
    # Check if bwa is available
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

    # Setup: Copy test reference to cache directory
    fixtures_ref_dir = TEST_ROOT / "fixtures" / "reference"

    # Create a PinataClient and pre-populate cache
    client = PinataClient()
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    # Create test CIDs for all files
    test_cid_fasta = "QmTestBwaFasta456"
    cached_fasta = client.cache_dir / test_cid_fasta
    shutil.copy(fixtures_ref_dir / "GRCh38_chr21.fasta", cached_fasta)

    files_list = [
        IpFile(
            id="test-id-fasta",
            cid=test_cid_fasta,
            name="GRCh38_chr21.fasta",
            size=cached_fasta.stat().st_size,
            keyvalues={"type": "reference"},
            created_at=datetime.now(),
        )
    ]

    # Add all index files if they exist in fixtures
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for i, ext in enumerate(index_extensions):
        index_fixture = fixtures_ref_dir / f"GRCh38_chr21.fasta{ext}"
        if index_fixture.exists():
            test_cid_index = f"QmTestBwaIndex{i}"
            cached_index = client.cache_dir / test_cid_index
            shutil.copy(index_fixture, cached_index)

            files_list.append(
                IpFile(
                    id=f"test-id-{ext}",
                    cid=test_cid_index,
                    name=f"GRCh38_chr21.fasta{ext}",
                    size=cached_index.stat().st_size,
                    keyvalues={"type": "reference"},
                    created_at=datetime.now(),
                )
            )

    ref = Reference(
        ref_name="GRCh38_chr21.fasta",
        files=files_list,
        client=client,
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
        cached_index = client.cache_dir / f"QmTestBwaIndex{i}"
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
