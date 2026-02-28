"""
Tests for samtools tasks.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.general.samtools import samtools_faidx
from stargazer.types import Reference
from stargazer.types.reference import ReferenceFile, ReferenceIndex


@pytest.mark.asyncio
async def test_samtools_faidx(fixtures_db):
    """Test samtools faidx creates .fai index file."""
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    ref_fasta = ReferenceFile(
        path=FIXTURES_DIR / "GRCh38_TP53.fa",
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
    )

    ref = Reference(build="GRCh38", fasta=ref_fasta)

    fixtures_db()  # checkout: switch to isolated work dir

    result = await samtools_faidx(ref)

    assert isinstance(result, Reference)
    assert result.build == "GRCh38"

    fai = result.faidx
    assert fai is not None, "Should have faidx file"
    assert fai.keyvalues.get("tool") == "samtools_faidx"
    assert fai.keyvalues.get("type") == "reference"
    assert fai.keyvalues.get("component") == "faidx"
    assert fai.keyvalues.get("build") == "GRCh38"
    assert fai.path is not None
    assert fai.path.exists()


@pytest.mark.asyncio
async def test_samtools_faidx_idempotent(fixtures_db):
    """Test that samtools_faidx is idempotent (doesn't fail if .fai already exists)."""
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    ref_fasta = ReferenceFile(
        path=FIXTURES_DIR / "GRCh38_TP53.fa",
        keyvalues={"type": "reference", "component": "fasta"},
    )
    fai_file = ReferenceIndex(
        path=FIXTURES_DIR / "GRCh38_TP53.fa.fai",
        keyvalues={"type": "reference", "component": "faidx"},
    )

    ref = Reference(build="GRCh38", fasta=ref_fasta, faidx=fai_file)

    fixtures_db()  # checkout

    result = await samtools_faidx(ref)

    assert isinstance(result, Reference)
    assert result.faidx is not None


@pytest.mark.asyncio
async def test_samtools_faidx_missing_file():
    """Test that samtools_faidx raises error when reference file is missing."""
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    ref = Reference(build="nonexistent.fasta")

    with pytest.raises(ValueError, match="No files to fetch"):
        await samtools_faidx(ref)
