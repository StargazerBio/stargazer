"""Tests for `app.user_state`: the dashboard's rows in the state table.

SQLite here; tests/postgres/ reruns them on Postgres and as a DSQL login.
"""

import asyncio

import pytest

from app import assets as assets_mod
from app import user_state
from stargazer.utils.index import SqliteIndex


@pytest.fixture
def state_index(tmp_path, monkeypatch):
    """The dashboard's index, in a temp dir."""
    index = SqliteIndex(tmp_path / "index.db")
    monkeypatch.setattr(assets_mod, "_index", index)
    return index


async def test_a_set_value_reads_back(state_index):
    """`put` then `get` gives the value; a key never set is None."""
    await user_state.put("launch:qc:edit", '{"run": "r1"}')
    assert await user_state.get("launch:qc:edit") == '{"run": "r1"}'
    assert await user_state.get("launch:other:edit") is None


async def test_put_replaces_the_value(state_index):
    """A second `put` of a key replaces its value."""
    await user_state.put("k", "one")
    await user_state.put("k", "two")
    assert await user_state.get("k") == "two"


async def test_with_prefix_takes_only_the_prefix(state_index):
    """`with_prefix` returns the keys under a prefix, read literally (no wildcards)."""
    await user_state.put("launch:a_b:edit", "1")
    await user_state.put("launch:c:run", "2")
    await user_state.put("launchXa:edit", "3")
    await user_state.put("settings:x", "4")
    assert await user_state.with_prefix("launch:") == {
        "launch:a_b:edit": "1",
        "launch:c:run": "2",
    }
    assert await user_state.with_prefix("launch:a_") == {"launch:a_b:edit": "1"}


async def test_delete_removes_the_key(state_index):
    """`delete` removes a key and says it did; a missing key says it didn't."""
    await user_state.put("k", "v")
    assert await user_state.delete("k") is True
    assert await user_state.get("k") is None
    assert await user_state.delete("k") is False


async def test_delete_with_a_value_only_takes_that_value(state_index):
    """A conditional delete leaves a key whose value has changed."""
    await user_state.put("k", "new")
    assert await user_state.delete("k", value="old") is False
    assert await user_state.get("k") == "new"
    assert await user_state.delete("k", value="new") is True


async def test_concurrent_conditional_deletes_take_it_once(state_index):
    """Of many deletes of the same value at once, exactly one takes it."""
    await user_state.put("k", "v")
    taken = await asyncio.gather(*(user_state.delete("k", value="v") for _ in range(8)))
    assert taken.count(True) == 1


async def test_replace_only_takes_the_value_it_expects(state_index):
    """`replace` swaps a value only while the key still holds the old one."""
    await user_state.put("k", "new")
    assert await user_state.replace("k", "old", "mine") is False
    assert await user_state.get("k") == "new"
    assert await user_state.replace("k", "new", "mine") is True
    assert await user_state.get("k") == "mine"
    assert await user_state.replace("missing", "new", "mine") is False
    assert await user_state.get("missing") is None


async def test_concurrent_replaces_take_it_once(state_index):
    """Of many replaces of the same value at once, exactly one takes it."""
    await user_state.put("k", "v")
    taken = await asyncio.gather(
        *(user_state.replace("k", "v", f"claim-{n}") for n in range(8))
    )
    assert taken.count(True) == 1
    assert await user_state.get("k") == f"claim-{taken.index(True)}"
