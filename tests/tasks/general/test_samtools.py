"""
Tests for samtools tasks.
"""

from pathlib import Path

import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.assets import Reference, ReferenceIndex
from stargazer.tasks.general.samtools import samtools_faidx


@pytest.mark.asyncio
async def test_samtools_faidx():
    """Test samtools faidx creates .fai index file."""
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

    result = await samtools_faidx(ref)

    assert isinstance(result, ReferenceIndex)
    assert result.tool == "samtools_faidx"
    assert result.build == "GRCh38"
    assert result.path is not None
    assert (await result.fetch()).exists()
    assert result.path.name.endswith(".fai")


@pytest.mark.asyncio
async def test_samtools_faidx_missing_file():
    """Test that samtools_faidx raises error when reference file is missing."""
    ref = Reference(path=Path("/nonexistent/path/ref.fasta"), build="GRCh38")

    with pytest.raises((FileNotFoundError, RuntimeError)):
        await samtools_faidx(ref)
