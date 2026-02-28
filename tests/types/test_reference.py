"""
Tests for Reference type.
"""

import os
import tempfile

import pytest
from pathlib import Path
from stargazer.types import Reference
from stargazer.types.reference import ReferenceFile, ReferenceIndex, AlignerIndex
import stargazer.utils.storage as _storage_mod


@pytest.mark.asyncio
async def test_update_components_local_only():
    """Test component update() methods in local-only mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        test_fasta = tmpdir_path / "GRCh38.fa"
        test_faidx = tmpdir_path / "GRCh38.fa.fai"
        test_bwt = tmpdir_path / "GRCh38.fa.bwt"

        test_fasta.write_text(">chr1\nATCGATCG\n")
        test_faidx.write_text("chr1\t8\t0\t9\t10\n")
        test_bwt.write_bytes(b"BWT_INDEX")

        fasta = ReferenceFile()
        await fasta.update(test_fasta, build="GRCh38")

        faidx = ReferenceIndex()
        await faidx.update(test_faidx, build="GRCh38")

        bwt = AlignerIndex()
        await bwt.update(test_bwt, build="GRCh38", aligner="bwa")

        ref = Reference(build="GRCh38", fasta=fasta, faidx=faidx, aligner_index=[bwt])

        assert ref.fasta is not None
        assert ref.faidx is not None
        assert len(ref.aligner_index) == 1

        # All files have local CIDs after upload
        assert ref.fasta.cid.startswith("local_")
        assert ref.faidx.cid.startswith("local_")
        assert ref.aligner_index[0].cid.startswith("local_")

        # Files exist in cache under their original names
        cache_fasta = _storage_mod.default_client.local_dir / test_fasta.name
        cache_faidx = _storage_mod.default_client.local_dir / test_faidx.name
        cache_bwt = _storage_mod.default_client.local_dir / test_bwt.name

        assert cache_fasta.exists()
        assert cache_faidx.exists()
        assert cache_bwt.exists()

        assert cache_fasta.read_text() == ">chr1\nATCGATCG\n"
        assert cache_faidx.read_text() == "chr1\t8\t0\t9\t10\n"
        assert cache_bwt.read_bytes() == b"BWT_INDEX"


@pytest.mark.asyncio
async def test_reference_fetch():
    """Test fetch() downloads all reference components."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        test_fasta = tmpdir_path / "GRCh38.fa"
        test_faidx = tmpdir_path / "GRCh38.fa.fai"

        test_fasta.write_text(">chr1\nATCGATCG\n")
        test_faidx.write_text("chr1\t8\t0\t9\t10\n")

        fasta = ReferenceFile()
        await fasta.update(test_fasta, build="GRCh38")

        faidx = ReferenceIndex()
        await faidx.update(test_faidx, build="GRCh38")

        ref = Reference(build="GRCh38", fasta=fasta, faidx=faidx)

        # Fetch (in local-only mode, files already have path set after update)
        cache_dir = await ref.fetch()

        assert cache_dir == _storage_mod.default_client.local_dir
        assert cache_dir.exists()

        # After fetch, path is set
        assert ref.fasta.path is not None
        assert ref.fasta.path.exists()
        assert ref.faidx.path is not None
        assert ref.faidx.path.exists()


@pytest.mark.asyncio
async def test_reference_fetch_empty():
    """Test fetch() raises ValueError for empty reference."""
    ref = Reference(build="GRCh38")

    with pytest.raises(ValueError, match="No files to fetch"):
        await ref.fetch()


def test_stargazer_mode_resolution():
    """Test that resolve_mode() correctly parses STARGAZER_MODE env var."""
    from stargazer.utils.storage import resolve_mode, StargazerMode

    original = os.environ.pop("STARGAZER_MODE", None)

    try:
        os.environ.pop("STARGAZER_MODE", None)
        assert resolve_mode() == StargazerMode.LOCAL

        os.environ["STARGAZER_MODE"] = "local"
        assert resolve_mode() == StargazerMode.LOCAL

        os.environ["STARGAZER_MODE"] = "cloud"
        assert resolve_mode() == StargazerMode.CLOUD

        os.environ["STARGAZER_MODE"] = "CLOUD"
        assert resolve_mode() == StargazerMode.CLOUD

        os.environ["STARGAZER_MODE"] = "invalid"
        with pytest.raises(ValueError, match="Invalid STARGAZER_MODE"):
            resolve_mode()
    finally:
        if original is not None:
            os.environ["STARGAZER_MODE"] = original
        else:
            os.environ.pop("STARGAZER_MODE", None)
