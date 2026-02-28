"""
Tests for samtools tasks.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

import stargazer.utils.storage as _storage_mod
from stargazer.tasks.general.samtools import samtools_faidx
from stargazer.types import Reference
from stargazer.types.reference import ReferenceFile, ReferenceIndex


@pytest.mark.asyncio
async def test_samtools_faidx():
    """Test samtools faidx creates .fai index file."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Copy test reference to cache directory
    ref_fixture = FIXTURES_DIR / "GRCh38_TP53.fa"
    assert ref_fixture.exists(), f"Test fixture not found: {ref_fixture}"

    # Pre-populate cache using _storage_mod.default_client
    test_cid = "QmTestTP53Fasta"
    cached_fasta = _storage_mod.default_client.local_dir / test_cid
    _storage_mod.default_client.local_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ref_fixture, cached_fasta)

    # Create a Reference with the cached file
    fasta_file = ReferenceFile(
        cid=test_cid,
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
            "env": "test",
        },
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
    fai = result.faidx
    assert fai is not None, "Should have faidx file"

    # Verify .fai file has metadata
    assert fai.keyvalues.get("tool") == "samtools_faidx", "Should have tool metadata"
    assert fai.keyvalues.get("type") == "reference", "Should have type metadata"
    assert fai.keyvalues.get("component") == "faidx", "Should have component metadata"
    assert fai.keyvalues.get("build") == "GRCh38", (
        "Should copy build metadata from reference"
    )

    # Verify .fai file exists at path
    assert fai.path is not None, "Should have path set"
    assert fai.path.exists(), "Index file should exist at path"


@pytest.mark.asyncio
async def test_samtools_faidx_idempotent():
    """Test that samtools_faidx is idempotent (doesn't fail if .fai already exists)."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Copy test reference to cache directory
    fixtures_ref_dir = FIXTURES_DIR

    # Pre-populate cache using _storage_mod.default_client
    _storage_mod.default_client.local_dir.mkdir(parents=True, exist_ok=True)

    test_cid_fasta = "QmTestTP53FastaIdempotent"
    test_cid_fai = "QmTestTP53FAI"
    cached_fasta = _storage_mod.default_client.local_dir / test_cid_fasta
    cached_fai = _storage_mod.default_client.local_dir / test_cid_fai
    shutil.copy(fixtures_ref_dir / "GRCh38_TP53.fa", cached_fasta)
    shutil.copy(fixtures_ref_dir / "GRCh38_TP53.fa.fai", cached_fai)

    # Create Reference with both files already present
    fasta_file = ReferenceFile(
        cid=test_cid_fasta,
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "env": "test",
        },
    )

    fai_file = ReferenceIndex(
        cid=test_cid_fai,
        keyvalues={
            "type": "reference",
            "component": "faidx",
            "env": "test",
        },
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
