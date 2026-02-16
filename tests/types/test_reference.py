"""
Tests for Reference type.

Tests cover:
- Hydrating references from Pinata
- Adding files to reference (IPFS and local-only mode)
"""

import os
import tempfile
import pytest
from pathlib import Path
from stargazer.types import Reference
from stargazer.utils.storage import default_client


@pytest.mark.asyncio
async def test_update_fasta():
    """Test update_fasta() uploads FASTA file."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Create temporary test file
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test FASTA file
        test_fasta = tmpdir_path / "GRCh38.fa"
        test_fasta.write_text(">chr1\nATCGATCG\n")

        # Create reference and update fasta component
        ref = Reference(build="GRCh38")

        fasta_ipfile = await ref.update_fasta(test_fasta)

        # Verify FASTA component was set
        assert ref.fasta is not None
        assert ref.fasta == fasta_ipfile
        assert ref.fasta.keyvalues.get("type") == "reference"
        assert ref.fasta.keyvalues.get("component") == "fasta"
        assert ref.fasta.keyvalues.get("build") == "GRCh38"


@pytest.mark.asyncio
async def test_update_faidx():
    """Test update_faidx() uploads FASTA index file."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Create temporary test file
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test FAIDX file
        test_faidx = tmpdir_path / "GRCh38.fa.fai"
        test_faidx.write_text("chr1\t8\t0\t9\t10\n")

        # Create reference and update faidx component
        ref = Reference(build="GRCh38")

        faidx_ipfile = await ref.update_faidx(test_faidx)

        # Verify FAIDX component was set
        assert ref.faidx is not None
        assert ref.faidx == faidx_ipfile
        assert ref.faidx.keyvalues.get("type") == "reference"
        assert ref.faidx.keyvalues.get("component") == "faidx"
        assert ref.faidx.keyvalues.get("build") == "GRCh38"


@pytest.mark.asyncio
async def test_update_aligner_index():
    """Test update_aligner_index() uploads aligner index files."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Create temporary test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test aligner index files (BWA)
        test_bwt = tmpdir_path / "GRCh38.fa.bwt"
        test_pac = tmpdir_path / "GRCh38.fa.pac"
        test_bwt.write_bytes(b"BWT_INDEX")
        test_pac.write_bytes(b"PAC_INDEX")

        # Create reference and update aligner index components
        ref = Reference(build="GRCh38")

        bwt_ipfile = await ref.update_aligner_index(test_bwt, aligner="bwa")
        pac_ipfile = await ref.update_aligner_index(test_pac, aligner="bwa")

        # Verify aligner index components were appended
        assert len(ref.aligner_index) == 2
        assert ref.aligner_index[0] == bwt_ipfile
        assert ref.aligner_index[1] == pac_ipfile
        assert all(f.keyvalues.get("type") == "reference" for f in ref.aligner_index)
        assert all(
            f.keyvalues.get("component") == "aligner_index" for f in ref.aligner_index
        )
        assert all(f.keyvalues.get("aligner") == "bwa" for f in ref.aligner_index)
        assert all(f.keyvalues.get("build") == "GRCh38" for f in ref.aligner_index)


@pytest.mark.asyncio
async def test_update_components_local_only():
    """Test update_*() methods in local-only mode."""
    try:
        # Create temporary test files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            test_fasta = tmpdir_path / "GRCh38.fa"
            test_faidx = tmpdir_path / "GRCh38.fa.fai"
            test_bwt = tmpdir_path / "GRCh38.fa.bwt"

            test_fasta.write_text(">chr1\nATCGATCG\n")
            test_faidx.write_text("chr1\t8\t0\t9\t10\n")
            test_bwt.write_bytes(b"BWT_INDEX")

            # Create reference and update components
            ref = Reference(build="GRCh38")

            await ref.update_fasta(test_fasta)
            await ref.update_faidx(test_faidx)
            await ref.update_aligner_index(test_bwt, aligner="bwa")

            # Verify components were set
            assert ref.fasta is not None
            assert ref.faidx is not None
            assert len(ref.aligner_index) == 1

            # Verify all files have local CIDs
            assert ref.fasta.cid.startswith("local_")
            assert ref.faidx.cid.startswith("local_")
            assert ref.aligner_index[0].cid.startswith("local_")

            # Verify files exist in cache
            cache_fasta = default_client.local_dir / ref.fasta.cid
            cache_faidx = default_client.local_dir / ref.faidx.cid
            cache_bwt = default_client.local_dir / ref.aligner_index[0].cid

            assert cache_fasta.exists()
            assert cache_faidx.exists()
            assert cache_bwt.exists()

            # Verify file contents match original
            assert cache_fasta.read_text() == ">chr1\nATCGATCG\n"
            assert cache_faidx.read_text() == "chr1\t8\t0\t9\t10\n"
            assert cache_bwt.read_bytes() == b"BWT_INDEX"
    finally:
        pass


@pytest.mark.asyncio
async def test_reference_fetch():
    """Test fetch() downloads all reference components."""
    try:
        # Create temporary test files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            test_fasta = tmpdir_path / "GRCh38.fa"
            test_faidx = tmpdir_path / "GRCh38.fa.fai"

            test_fasta.write_text(">chr1\nATCGATCG\n")
            test_faidx.write_text("chr1\t8\t0\t9\t10\n")

            # Create reference and update components
            ref = Reference(build="GRCh38")
            await ref.update_fasta(test_fasta)
            await ref.update_faidx(test_faidx)

            # Fetch components (in local-only mode, they're already there)
            cache_dir = await ref.fetch()

            # Verify cache directory returned
            assert cache_dir == default_client.local_dir
            assert cache_dir.exists()

            # Verify both files are in cache (check local_path is set)
            assert ref.fasta.local_path is not None
            assert ref.fasta.local_path.exists()
            assert ref.faidx.local_path is not None
            assert ref.faidx.local_path.exists()

            # Cleanup
            if ref.fasta.local_path.exists():
                ref.fasta.local_path.unlink()
            if ref.faidx.local_path.exists():
                ref.faidx.local_path.unlink()
            for idx in ref.aligner_index:
                if idx.local_path and idx.local_path.exists():
                    idx.local_path.unlink()
    finally:
        pass


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
        # Default is local
        os.environ.pop("STARGAZER_MODE", None)
        assert resolve_mode() == StargazerMode.LOCAL

        # Explicit local
        os.environ["STARGAZER_MODE"] = "local"
        assert resolve_mode() == StargazerMode.LOCAL

        # Cloud mode
        os.environ["STARGAZER_MODE"] = "cloud"
        assert resolve_mode() == StargazerMode.CLOUD

        # Case insensitive
        os.environ["STARGAZER_MODE"] = "CLOUD"
        assert resolve_mode() == StargazerMode.CLOUD

        # Invalid value raises
        os.environ["STARGAZER_MODE"] = "invalid"
        with pytest.raises(ValueError, match="Invalid STARGAZER_MODE"):
            resolve_mode()
    finally:
        if original is not None:
            os.environ["STARGAZER_MODE"] = original
        else:
            os.environ.pop("STARGAZER_MODE", None)
