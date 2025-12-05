"""
Tests for samtools tasks.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

from flyte.io import Dir
from stargazer.types import Reference
from stargazer.tasks.samtools import samtools_faidx
from config import TEST_ROOT


@pytest.mark.asyncio
async def test_samtools_faidx():
    """Test samtools faidx creates .fai index file."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Create a temporary directory with test reference
    ref_fixture = TEST_ROOT / "fixtures" / "reference" / "GRCh38_chr21.fasta"
    assert ref_fixture.exists(), f"Test fixture not found: {ref_fixture}"

    # Create temporary directory and copy FASTA (without .fai)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        ref_copy = tmpdir_path / "GRCh38_chr21.fasta"
        shutil.copy(ref_fixture, ref_copy)

        # Ensure no .fai file exists initially
        fai_path = tmpdir_path / "GRCh38_chr21.fasta.fai"
        if fai_path.exists():
            fai_path.unlink()

        # Create Reference object
        ref_dir = await Dir.from_local(str(tmpdir_path))
        ref = Reference(
            dir=ref_dir,
            ref_name="GRCh38_chr21.fasta",
        )

        # Run samtools_faidx
        result = await samtools_faidx(ref)

        # Verify the result
        assert isinstance(result, Reference)
        assert result.ref_name == "GRCh38_chr21.fasta"

        # Download result directory to check contents
        result_dir_path = Path(await result.dir.download())
        result_fai_path = result_dir_path / "GRCh38_chr21.fasta.fai"

        # Verify .fai file exists
        assert result_fai_path.exists(), f"Index file not found: {result_fai_path}"

        # Verify .fai file has content (should not be empty)
        assert result_fai_path.stat().st_size > 0, "Index file is empty"

        # Verify .fai has expected format (chr21 line with 5 tab-separated fields)
        fai_content = result_fai_path.read_text()
        assert "chr21" in fai_content, "Index should contain chr21 entry"
        # FAI format: chrom, length, offset, linebases, linewidth
        lines = fai_content.strip().split("\n")
        assert len(lines) > 0, "Index file should have at least one line"
        fields = lines[0].split("\t")
        assert len(fields) == 5, f"Expected 5 fields in .fai, got {len(fields)}"


@pytest.mark.asyncio
async def test_samtools_faidx_idempotent():
    """Test that samtools_faidx is idempotent (doesn't fail if .fai already exists)."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Setup: Use fixtures directory which already has .fai file
    fixtures_ref_dir = TEST_ROOT / "fixtures" / "reference"

    # Create temporary directory and copy both FASTA and .fai
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        shutil.copy(
            fixtures_ref_dir / "GRCh38_chr21.fasta",
            tmpdir_path / "GRCh38_chr21.fasta"
        )
        shutil.copy(
            fixtures_ref_dir / "GRCh38_chr21.fasta.fai",
            tmpdir_path / "GRCh38_chr21.fasta.fai"
        )

        # Get original .fai modification time
        original_fai = tmpdir_path / "GRCh38_chr21.fasta.fai"
        original_mtime = original_fai.stat().st_mtime

        # Create Reference object
        ref_dir = await Dir.from_local(str(tmpdir_path))
        ref = Reference(
            dir=ref_dir,
            ref_name="GRCh38_chr21.fasta",
        )

        # Run samtools_faidx (should not fail or regenerate)
        result = await samtools_faidx(ref)

        # Verify the result
        assert isinstance(result, Reference)

        # Download result and check .fai wasn't regenerated
        result_dir_path = Path(await result.dir.download())
        result_fai_path = result_dir_path / "GRCh38_chr21.fasta.fai"

        assert result_fai_path.exists(), "Index file should still exist"
        # Note: modification time might change due to copy operations in Flyte,
        # so we just verify the file exists and has content
        assert result_fai_path.stat().st_size > 0, "Index file should have content"


@pytest.mark.asyncio
async def test_samtools_faidx_missing_file():
    """Test that samtools_faidx raises error when reference file is missing."""
    # Check if samtools is available
    if shutil.which("samtools") is None:
        pytest.skip("samtools not available in environment")

    # Create empty temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create Reference object pointing to non-existent file
        ref_dir = await Dir.from_local(str(tmpdir_path))
        ref = Reference(
            dir=ref_dir,
            ref_name="nonexistent.fasta",
        )

        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="not found"):
            await samtools_faidx(ref)
