"""
Tests for Reference asset types.
"""

import tempfile
from pathlib import Path

import pytest

import stargazer.utils.storage as _storage_mod
from stargazer.assets import specialize
from stargazer.assets.reference import (
    AlignerIndex,
    Reference,
    ReferenceIndex,
    SequenceDict,
)
from stargazer.utils.cid import compute_cid


@pytest.mark.asyncio
async def test_update_components_local_only():
    """update() gives each file its IPFS CID and seeds the local cache under it."""
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

        assert fasta.cid == compute_cid(test_fasta)
        assert faidx.cid == compute_cid(test_faidx)
        assert bwt.cid == compute_cid(test_bwt)

        assert fasta.build == "GRCh38"
        assert faidx.build == "GRCh38"
        assert bwt.build == "GRCh38"
        assert bwt.aligner == "bwa"

        cache_dir = _storage_mod.default_client.local_dir
        assert (cache_dir / fasta.cid / "GRCh38.fa").read_text() == ">chr1\nATCGATCG\n"
        assert (
            cache_dir / faidx.cid / "GRCh38.fa.fai"
        ).read_text() == "chr1\t8\t0\t9\t10\n"
        assert (cache_dir / bwt.cid / "GRCh38.fa.bwt").read_bytes() == b"BWT_INDEX"


@pytest.mark.asyncio
async def test_reference_fetch(fixtures_db):
    """Test query + specialize resolves local copies from the store."""
    [fasta_r] = await _storage_mod.default_client.query(
        {"asset": "reference", "build": "GRCh38"}
    )
    [faidx_r] = await _storage_mod.default_client.query(
        {"asset": "reference_index", "build": "GRCh38"}
    )

    fasta = specialize(fasta_r)
    faidx = specialize(faidx_r)

    assert fasta.path is not None
    assert (await fasta.fetch()).exists()
    assert faidx.path is not None
    assert (await faidx.fetch()).exists()


@pytest.mark.asyncio
async def test_reference_contigs_from_the_store(fixtures_db):
    """contigs() reads a stored reference's index, as a pod that didn't make it would."""
    [fasta_r] = await _storage_mod.default_client.query(
        {"asset": "reference", "build": "GRCh38"}
    )

    assert await specialize(fasta_r).contigs() == ["chr17:7658421-7697490"]


@pytest.mark.asyncio
async def test_reference_aligner_index_query(fixtures_db):
    """Test querying multiple aligner index files."""
    results = await _storage_mod.default_client.query(
        {"asset": "aligner_index", "build": "GRCh38", "aligner": "bwa"}
    )
    assert len(results) > 0
    for r in results:
        assert r["keyvalues"].get("asset") == "aligner_index"
        assert r["keyvalues"].get("aligner") == "bwa"


@pytest.mark.asyncio
async def test_sequence_dict_asset():
    """Test SequenceDict asset fields."""
    sd = SequenceDict()
    sd.build = "GRCh38"
    assert sd._asset_key == "sequence_dict"
    assert sd.build == "GRCh38"
