"""Tests for the SQLite asset index."""

import asyncio
import sqlite3

import pytest

from stargazer.config import logger
from stargazer.utils.index import SqliteIndex


def _record(cid: str, **keyvalues: str) -> dict:
    """A row as the storage client writes it."""
    return {
        "cid": cid,
        "uri": f"/store/users/local/assets/{cid}/{cid}.bin",
        "name": f"{cid}.bin",
        "keyvalues": keyvalues,
    }


@pytest.fixture
def index(tmp_path):
    """A fresh index in a temp dir."""
    return SqliteIndex(tmp_path / "index.db")


@pytest.fixture
def warnings():
    """Collect WARNING-and-above log messages."""
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="WARNING")
    yield messages
    logger.remove(sink)


@pytest.mark.asyncio
async def test_round_trip(index):
    """An upserted row comes back from a query on its keyvalues."""
    await index.upsert(_record("bafyA", asset="alignment", sample_id="S1"))

    [row] = await index.query({"asset": "alignment", "sample_id": "S1"})

    assert row["cid"] == "bafyA"
    assert row["uri"] == "/store/users/local/assets/bafyA/bafyA.bin"
    assert row["name"] == "bafyA.bin"
    assert row["keyvalues"] == {"asset": "alignment", "sample_id": "S1"}


@pytest.mark.asyncio
async def test_exact_match(index):
    """A row missing a filter key, or holding another value, doesn't match."""
    await index.upsert(_record("bafyA", asset="alignment", sample_id="S1"))
    await index.upsert(_record("bafyB", asset="alignment", sample_id="S2"))
    await index.upsert(_record("bafyC", asset="alignment"))

    rows = await index.query({"asset": "alignment", "sample_id": "S1"})

    assert [r["cid"] for r in rows] == ["bafyA"]


@pytest.mark.asyncio
async def test_list_filter_matches_any(index):
    """A list value matches any of its entries, in one call."""
    for cid, sample in (("bafyA", "S1"), ("bafyB", "S2"), ("bafyC", "S3")):
        await index.upsert(_record(cid, asset="r1", sample_id=sample))

    rows = await index.query({"asset": "r1", "sample_id": ["S1", "S3"]})

    assert sorted(r["cid"] for r in rows) == ["bafyA", "bafyC"]


@pytest.mark.asyncio
async def test_companion_lookup(index):
    """A `<asset_key>_cid` filter returns only that parent's companions."""
    await index.upsert(_record("bafyBam", asset="alignment"))
    await index.upsert(
        _record("bafyBai", asset="alignment_index", alignment_cid="bafyBam")
    )
    await index.upsert(
        _record("bafyOther", asset="alignment_index", alignment_cid="bafyX")
    )

    rows = await index.query({"alignment_cid": "bafyBam"})

    assert [r["cid"] for r in rows] == ["bafyBai"]


@pytest.mark.asyncio
async def test_same_row_twice_is_one_row_without_warning(index, warnings):
    """Re-upserting identical metadata keeps one row and stays quiet."""
    await index.upsert(_record("bafyA", asset="alignment", sample_id="S1"))
    await index.upsert(_record("bafyA", asset="alignment", sample_id="S1"))

    rows = await index.query({})

    assert len(rows) == 1
    assert warnings == []


@pytest.mark.asyncio
async def test_new_metadata_replaces_and_warns(index, warnings):
    """Same CID, different keyvalues: the new ones win and a WARNING names what changed."""
    await index.upsert(_record("bafyA", asset="alignment", sample_id="S1", tool="bwa"))
    await index.upsert(_record("bafyA", asset="alignment", sample_id="S2", tool="bwa"))

    [row] = await index.query({})

    assert row["keyvalues"] == {"asset": "alignment", "sample_id": "S2", "tool": "bwa"}
    assert len(warnings) == 1
    assert "bafyA" in warnings[0]
    assert "sample_id" in warnings[0]
    assert "tool" not in warnings[0]


@pytest.mark.asyncio
async def test_concurrent_merges_keep_every_key(index):
    """Twenty merges on one row at once each land."""
    await index.upsert(_record("bafyA", asset="alignment"))

    await asyncio.gather(*(index.merge("bafyA", {f"k{i}": str(i)}) for i in range(20)))

    [row] = await index.query({})
    assert {f"k{i}": str(i) for i in range(20)}.items() <= row["keyvalues"].items()
    assert row["keyvalues"]["asset"] == "alignment"


@pytest.mark.asyncio
async def test_merge_missing_row_raises(index):
    """Merging onto a CID with no row is an error, not a silent insert."""
    with pytest.raises(ValueError, match="bafyNope"):
        await index.merge("bafyNope", {"asset": "alignment"})


@pytest.mark.asyncio
async def test_delete_is_idempotent(index):
    """Deleting removes the row; deleting again is a no-op."""
    await index.upsert(_record("bafyA", asset="alignment"))

    await index.delete("bafyA")
    await index.delete("bafyA")

    assert await index.query({}) == []
    assert await index.get("bafyA") is None


@pytest.mark.asyncio
async def test_read_during_a_held_write(index, tmp_path):
    """A query while another connection holds an exclusive write lock returns committed rows without waiting."""
    await index.upsert(_record("bafyA", asset="alignment"))
    other = sqlite3.connect(tmp_path / "index.db", isolation_level=None)
    other.execute("BEGIN EXCLUSIVE")
    other.execute(
        "INSERT INTO assets (cid, uri, name, keyvalues, created_at) VALUES ('bafyB', 'u', 'n', '{}', 't')"
    )
    try:
        rows = await asyncio.wait_for(index.query({}), timeout=2)
    finally:
        other.execute("ROLLBACK")
        other.close()

    assert [r["cid"] for r in rows] == ["bafyA"]
