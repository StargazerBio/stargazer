"""
Tests for BWA tasks.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.general.bwa import bwa_index
from stargazer.types import Reference
from stargazer.types.reference import ReferenceFile, AlignerIndex


@pytest.mark.asyncio
async def test_bwa_index(fixtures_db):
    """Test bwa index creates all index files (.amb, .ann, .bwt, .pac, .sa)."""
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

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

    result = await bwa_index(ref)

    assert isinstance(result, Reference)
    assert result.build == "GRCh38"
    assert len(result.aligner_index) == 5, "Should have exactly 5 BWA index files"

    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for ext in index_extensions:
        matching = [
            f
            for f in result.aligner_index
            if f and f.path and f.path.name.endswith(ext)
        ]
        assert len(matching) == 1, f"Should have exactly one {ext} file"

        idx = matching[0]
        assert idx.keyvalues.get("aligner") == "bwa"
        assert idx.keyvalues.get("type") == "reference"
        assert idx.keyvalues.get("component") == "aligner_index"
        assert idx.keyvalues.get("build") == "GRCh38"
        assert idx.path is not None
        assert idx.path.exists()


@pytest.mark.asyncio
async def test_bwa_index_idempotent(fixtures_db):
    """Test that bwa_index is idempotent (doesn't fail if index files already exist)."""
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    aligner_index_files = [
        AlignerIndex(
            path=FIXTURES_DIR / f"GRCh38_TP53.fa{ext}",
            keyvalues={
                "type": "reference",
                "component": "aligner_index",
                "aligner": "bwa",
            },
        )
        for ext in index_extensions
        if (FIXTURES_DIR / f"GRCh38_TP53.fa{ext}").exists()
    ]

    ref = Reference(
        build="GRCh38",
        fasta=ReferenceFile(
            path=FIXTURES_DIR / "GRCh38_TP53.fa",
            keyvalues={"type": "reference", "component": "fasta"},
        ),
        aligner_index=aligner_index_files,
    )

    fixtures_db()  # checkout

    result = await bwa_index(ref)

    assert isinstance(result, Reference)
    assert len(result.aligner_index) == len(aligner_index_files), (
        "Should not duplicate index files"
    )


@pytest.mark.asyncio
async def test_bwa_index_missing_file():
    """Test that bwa_index raises error when reference file is missing."""
    if shutil.which("bwa") is None:
        pytest.skip("bwa not available in environment")

    ref = Reference(build="nonexistent.fasta")

    with pytest.raises(ValueError, match="No files to fetch"):
        await bwa_index(ref)
