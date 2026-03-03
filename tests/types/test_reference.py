"""
Tests for Reference asset types.
"""

import os
import tempfile

import pytest
from pathlib import Path

import stargazer.utils.storage as _storage_mod
from stargazer.types.reference import (
    Reference,
    ReferenceIndex,
    AlignerIndex,
    SequenceDict,
)


@pytest.mark.asyncio
async def test_update_components_local_only():
    """Test asset update() methods in local-only mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        test_fasta = tmpdir_path / "GRCh38.fa"
        test_faidx = tmpdir_path / "GRCh38.fa.fai"
        test_bwt = tmpdir_path / "GRCh38.fa.bwt"

        test_fasta.write_text(">chr1\nATCGATCG\n")
        test_faidx.write_text("chr1\t8\t0\t9\t10\n")
        test_bwt.write_bytes(b"BWT_INDEX")

        fasta = Reference()
        await fasta.update(test_fasta, build="GRCh38")

        faidx = ReferenceIndex()
        await faidx.update(test_faidx, build="GRCh38")

        bwt = AlignerIndex()
        await bwt.update(test_bwt, build="GRCh38", aligner="bwa")

        # All files have local CIDs after upload
        assert fasta.cid.startswith("local_")
        assert faidx.cid.startswith("local_")
        assert bwt.cid.startswith("local_")

        # Keyvalues set correctly
        assert fasta.keyvalues.get("asset") == "reference"
        assert fasta.keyvalues.get("build") == "GRCh38"
        assert faidx.keyvalues.get("asset") == "reference_index"
        assert bwt.keyvalues.get("asset") == "aligner_index"
        assert bwt.keyvalues.get("aligner") == "bwa"

        # Files exist in cache under their original names
        cache_dir = _storage_mod.default_client.local_dir
        assert (cache_dir / test_fasta.name).exists()
        assert (cache_dir / test_faidx.name).exists()
        assert (cache_dir / test_bwt.name).exists()

        assert (cache_dir / test_fasta.name).read_text() == ">chr1\nATCGATCG\n"
        assert (cache_dir / test_faidx.name).read_text() == "chr1\t8\t0\t9\t10\n"
        assert (cache_dir / test_bwt.name).read_bytes() == b"BWT_INDEX"


@pytest.mark.asyncio
async def test_reference_fetch(fixtures_db):
    """Test individual asset download() resolves paths from CIDs via TinyDB."""
    [fasta_r] = await _storage_mod.default_client.query(
        {"asset": "reference", "build": "GRCh38"}
    )
    [faidx_r] = await _storage_mod.default_client.query(
        {"asset": "reference_index", "build": "GRCh38"}
    )

    # Download resolves paths
    await _storage_mod.default_client.download(fasta_r)
    await _storage_mod.default_client.download(faidx_r)

    assert fasta_r.path is not None
    assert fasta_r.path.exists()
    assert faidx_r.path is not None
    assert faidx_r.path.exists()


@pytest.mark.asyncio
async def test_reference_aligner_index_query(fixtures_db):
    """Test querying multiple aligner index files."""
    results = await _storage_mod.default_client.query(
        {"asset": "aligner_index", "build": "GRCh38", "aligner": "bwa"}
    )
    assert len(results) > 0
    for r in results:
        assert r.keyvalues.get("asset") == "aligner_index"
        assert r.keyvalues.get("aligner") == "bwa"


@pytest.mark.asyncio
async def test_sequence_dict_asset():
    """Test SequenceDict asset keyvalues."""
    sd = SequenceDict()
    sd.build = "GRCh38"
    assert sd.keyvalues.get("asset") == "sequence_dict"
    assert sd.build == "GRCh38"


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
