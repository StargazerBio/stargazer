"""
Tests for samtools tasks.
"""

import shutil
from datetime import datetime

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.general.samtools import samtools_faidx
from stargazer.types import Reference
from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_samtools_faidx():
    """Test samtools faidx creates .fai index file."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Copy test reference to cache directory
    ref_fixture = FIXTURES_DIR / "GRCh38_TP53.fa"
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

    # Run samtools_faidx - it will call ref.fetch() internally
    result = await samtools_faidx(ref)

    # Verify result
    assert isinstance(result, Reference)
    assert result.build == "GRCh38"

    # Verify .fai file was added to faidx component
    fai_files = result.faidx
    assert fai_files is not None, "Should have faidx file"
    assert fai_files.size > 0, "Index file should not be empty"

    # Verify .fai file has metadata
    assert fai_files.keyvalues.get("tool") == "samtools_faidx", (
        "Should have tool metadata"
    )
    assert fai_files.keyvalues.get("type") == "reference", "Should have type metadata"
    assert fai_files.keyvalues.get("component") == "faidx", (
        "Should have component metadata"
    )
    assert fai_files.keyvalues.get("build") == "GRCh38", (
        "Should copy build metadata from reference"
    )

    # Verify .fai file exists at local_path
    # Samtools creates files with CID as base name (e.g., QmTestTP53Fasta.fai)
    assert fai_files.local_path is not None, "Should have local_path set"
    assert fai_files.local_path.exists(), "Index file should exist at local_path"

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
    fixtures_ref_dir = FIXTURES_DIR

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
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "env": "test",
        },
        created_at=datetime.now(),
    )

    fai_file = IpFile(
        id="test-id-fai",
        cid=test_cid_fai,
        name="GRCh38_TP53.fa.fai",
        size=cached_fai.stat().st_size,
        keyvalues={
            "type": "reference",
            "component": "faidx",
            "env": "test",
        },
        created_at=datetime.now(),
    )

    ref = Reference(
        build="GRCh38",
        fasta=fasta_file,
        faidx=fai_file,
    )

    # Run samtools_faidx (should not regenerate)
    result = await samtools_faidx(ref)

    # Verify result
    assert isinstance(result, Reference)

    # Should still have faidx component
    assert result.faidx is not None, "Should have faidx file"

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

    # Create a Reference with empty fasta component
    ref = Reference(
        build="nonexistent.fasta",
    )

    # Should raise ValueError when trying to fetch empty reference
    with pytest.raises(ValueError, match="No files to fetch"):
        await samtools_faidx(ref)
