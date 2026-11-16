"""Tests for Asset.find() and Asset.find_all(): one type's assets by keyvalue."""

import pytest

from stargazer.assets.reads import R1, R2
from stargazer.assets.reference import Reference, ReferenceIndex


@pytest.fixture
def write(tmp_path):
    """Write a small file with unique contents and return its path."""

    def _write(name: str) -> object:
        path = tmp_path / "files" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"contents of {name}\n")
        return path

    return _write


async def test_find_returns_the_one_match_of_its_type(write):
    """find() skips other types under the same filters."""
    ref = await Reference.store(write("ref.fa"), build="GRCh38")
    await ReferenceIndex.store(write("ref.fa.fai"), build="GRCh38")

    found = await Reference.find(build="GRCh38")

    assert type(found) is Reference
    assert found.cid == ref.cid


async def test_find_picks_the_newest_of_several(write):
    """With more than one match, the one stored last wins."""
    await R1.store(write("old_R1.fq"), sample_id="S1")
    newest = await R1.store(write("new_R1.fq"), sample_id="S1")

    assert (await R1.find(sample_id="S1")).cid == newest.cid


async def test_find_raises_naming_the_type_and_filters(write):
    """A required find with no match says what it looked for."""
    await Reference.store(write("ref.fa"), build="GRCh38")

    with pytest.raises(ValueError, match=r"No Reference found for build='T2T'"):
        await Reference.find(build="T2T")


async def test_find_not_required_returns_none(write):
    """required=False turns a missing match into None."""
    await R1.store(write("s1_R1.fq"), sample_id="S1")

    assert await R2.find(sample_id="S1", required=False) is None


async def test_find_all_returns_every_match_of_its_type(write):
    """find_all() returns the type's matches, newest first, and nothing else."""
    first = await R1.store(write("a_R1.fq"), sample_id="S1")
    second = await R1.store(write("b_R1.fq"), sample_id="S1")
    await R2.store(write("a_R2.fq"), sample_id="S1")
    await R1.store(write("c_R1.fq"), sample_id="S2")

    found = await R1.find_all(sample_id="S1")

    assert [a.cid for a in found] == [second.cid, first.cid]
    assert {type(a) for a in found} == {R1}


async def test_find_all_empty(write):
    """find_all() with no matches returns an empty list."""
    await R1.store(write("s1_R1.fq"), sample_id="S1")

    assert await R1.find_all(sample_id="S9") == []
