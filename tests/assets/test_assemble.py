"""Tests for assemble() — storage query to specialized asset list."""

import pytest

from stargazer.assets.asset import assemble
from stargazer.assets.reads import R1, R2
from stargazer.assets.reference import AlignerIndex, Reference, ReferenceIndex


@pytest.fixture
def write(tmp_path):
    """Write a small file with unique contents and return its path."""

    def _write(name: str) -> object:
        path = tmp_path / "files" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"contents of {name}\n")
        return path

    return _write


@pytest.mark.asyncio
async def test_assemble_returns_specialized_list(write):
    """assemble() returns a flat list of specialized assets."""
    await Reference().update(write("ref.fa"), build="GRCh38")
    await ReferenceIndex().update(write("ref.fa.fai"), build="GRCh38")

    assets = await assemble(build="GRCh38")

    assert len(assets) == 2
    assert len([a for a in assets if isinstance(a, Reference)]) == 1
    assert len([a for a in assets if isinstance(a, ReferenceIndex)]) == 1


@pytest.mark.asyncio
async def test_assemble_list_filter_matches_any(write):
    """asset=["r1", "r2"] matches either asset type."""
    await R1().update(write("s1_R1.fq"), sample_id="S1")
    await R2().update(write("s1_R2.fq"), sample_id="S1")
    await R1().update(write("s2_R1.fq"), sample_id="S2")

    assets = await assemble(sample_id="S1", asset=["r1", "r2"])

    assert len([a for a in assets if isinstance(a, R1)]) == 1
    assert len([a for a in assets if isinstance(a, R2)]) == 1
    assert len(assets) == 2


@pytest.mark.asyncio
async def test_assemble_deduplicates_by_cid(write):
    """A repeated list value doesn't return the same asset twice."""
    await Reference().update(write("ref.fa"), build="GRCh38")

    assets = await assemble(build="GRCh38", asset=["reference", "reference"])

    assert len([a for a in assets if isinstance(a, Reference)]) == 1


@pytest.mark.asyncio
async def test_assemble_empty_result(write):
    """assemble() with no matches returns empty list."""
    await Reference().update(write("ref.fa"), build="GRCh38")

    assert await assemble(build="nonexistent") == []


@pytest.mark.asyncio
async def test_assemble_multiple_same_key(write):
    """Multiple results with same _asset_key all appear in the list."""
    await AlignerIndex().update(write("ref.fa.amb"), build="GRCh38", aligner="bwa")
    await AlignerIndex().update(write("ref.fa.ann"), build="GRCh38", aligner="bwa")

    assets = await assemble(build="GRCh38")

    assert len([a for a in assets if isinstance(a, AlignerIndex)]) == 2
