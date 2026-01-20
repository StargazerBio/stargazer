"""
Tests for samtools tasks.
"""

import shutil
from datetime import datetime

import pytest
from config import TEST_ROOT

from stargazer.tasks.samtools import samtools_faidx
from stargazer.types import Reference
from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_samtools_faidx():
    """Test samtools faidx creates .fai index file."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

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

    # Run samtools_faidx - it will call ref.fetch() internally
    result = await samtools_faidx(ref)

    # Verify the result
    assert isinstance(result, Reference)
    assert result.ref_name == "GRCh38_TP53.fa"

    # Verify .fai file was added to files list
    fai_files = [f for f in result.files if f.name == "GRCh38_TP53.fa.fai"]
    assert len(fai_files) == 1, "Should have exactly one .fai file"
    assert fai_files[0].size > 0, "Index file should not be empty"

    # Verify the .fai file has metadata
    assert fai_files[0].keyvalues.get("tool") == "samtools_faidx", (
        "Should have tool metadata"
    )
    assert fai_files[0].keyvalues.get("type") == "reference", (
        "Should have type metadata"
    )
    assert fai_files[0].keyvalues.get("build") == "GRCh38", (
        "Should copy build metadata from reference"
    )

    # Verify .fai file exists at local_path
    # Samtools creates files with the CID as base name (e.g., QmTestTP53Fasta.fai)
    assert fai_files[0].local_path is not None, "Should have local_path set"
    assert fai_files[0].local_path.exists(), "Index file should exist at local_path"

    # Cleanup - use actual cached filenames (CID-based)
    if cached_fasta.exists():
        cached_fasta.unlink()
    fai_path = cached_fasta.parent / f"{test_cid}.fai"
    if fai_path.exists():
        fai_path.unlink()


@pytest.mark.asyncio
async def test_samtools_faidx_idempotent():
    """Test that samtools_faidx is idempotent (doesn't fail if .fai already exists)."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Copy test reference to cache directory
    fixtures_ref_dir = TEST_ROOT / "fixtures"

    # Pre-populate cache using default_client
    default_client.local_dir.mkdir(parents=True, exist_ok=True)

    test_cid_fasta = "QmTestTP53FastaIdempotent"
    test_cid_fai = "QmTestTP53FAI"
    cached_fasta = default_client.local_dir / test_cid_fasta
    cached_fai = default_client.local_dir / test_cid_fai
    shutil.copy(fixtures_ref_dir / "GRCh38_TP53.fa", cached_fasta)
    shutil.copy(fixtures_ref_dir / "GRCh38_TP53.fa.fai", cached_fai)

    # Create Reference with both files already present
    fasta_file = IpFile(
        id="test-id-fasta",
        cid=test_cid_fasta,
        name="GRCh38_TP53.fa",
        size=cached_fasta.stat().st_size,
        keyvalues={"type": "reference", "env": "test"},
        created_at=datetime.now(),
    )

    fai_file = IpFile(
        id="test-id-fai",
        cid=test_cid_fai,
        name="GRCh38_TP53.fa.fai",
        size=cached_fai.stat().st_size,
        keyvalues={"type": "reference", "env": "test"},
        created_at=datetime.now(),
    )

    ref = Reference(
        ref_name="GRCh38_TP53.fa",
        files=[fasta_file, fai_file],
    )

    # Run samtools_faidx (should not regenerate)
    result = await samtools_faidx(ref)

    # Verify the result
    assert isinstance(result, Reference)

    # Should still have exactly 2 files (not 3)
    assert len(result.files) == 2, "Should not duplicate .fai file"

    # Verify .fai file exists
    fai_files = [f for f in result.files if f.name == "GRCh38_TP53.fa.fai"]
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
