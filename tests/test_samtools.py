"""
Tests for samtools tasks.
"""

import shutil
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

from stargazer.types import Reference
from stargazer.tasks.samtools import samtools_faidx
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

    # Create a mock PinataClient with cache directory
    client = PinataClient()

    # Copy fixture to cache (simulating a downloaded file)
    # PinataClient caches files as cache_dir / cid
    test_cid = "QmTestFasta123"
    cached_fasta = client.cache_dir / test_cid
    client.cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ref_fixture, cached_fasta)

    # Create a mock IpFile
    fasta_file = IpFile(
        id="test-id",
        cid=test_cid,
        name="GRCh38_chr21.fasta",
        size=cached_fasta.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38"},
        created_at=datetime.now(),
    )

    # Create Reference object with IpFile
    ref = Reference(
        ref_name="GRCh38_chr21.fasta",
        files=[fasta_file],
        client=client,
    )

    # Run samtools_faidx
    result = await samtools_faidx(ref)

    # Verify the result
    assert isinstance(result, Reference)
    assert result.ref_name == "GRCh38_chr21.fasta"

    # Verify .fai file was added to files list
    fai_files = [f for f in result.files if f.name == "GRCh38_chr21.fasta.fai"]
    assert len(fai_files) == 1, "Should have exactly one .fai file"
    assert fai_files[0].size > 0, "Index file should not be empty"

    # Cleanup
    if cached_fasta.exists():
        cached_fasta.unlink()


@pytest.mark.asyncio
async def test_samtools_faidx_idempotent():
    """Test that samtools_faidx is idempotent (doesn't fail if .fai already exists)."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Copy test reference to cache directory
    fixtures_ref_dir = TEST_ROOT / "fixtures" / "reference"

    # Create a mock PinataClient with cache directory
    client = PinataClient()
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    # Copy both FASTA and .fai to cache (using CID as filename)
    test_cid_fasta = "QmTestFasta456"
    test_cid_fai = "QmTestFai456"
    cached_fasta = client.cache_dir / test_cid_fasta
    cached_fai = client.cache_dir / test_cid_fai
    shutil.copy(fixtures_ref_dir / "GRCh38_chr21.fasta", cached_fasta)
    shutil.copy(fixtures_ref_dir / "GRCh38_chr21.fasta.fai", cached_fai)

    # Create mock IpFiles
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

    # Create Reference object with both files
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
        client=PinataClient(),
    )

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError, match="not found"):
        await samtools_faidx(ref)
