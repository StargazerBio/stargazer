"""
### The dashboard's own per-user state, in the state table beside the index.

One text value per key, in the owner's index's state table
(`SqlIndex.state_table`): their DSQL table's on Union, the devbox's
Postgres, a SQLite file locally. It outlives the dashboard process, so state
a restart must not lose lives here. Keys are namespaced by what owns them
(`launch:<slug>:<mode>`). Every call is its own transaction, on the index's
connection and its rerun on a serialization failure.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
from datetime import UTC, datetime

from app.assets import get_index


async def get(key: str) -> str | None:
    """The value at `key`, or None."""
    index = get_index()
    rows = await asyncio.to_thread(
        index.read, f"SELECT value FROM {index.state_table} WHERE key = ?", [key]
    )
    return rows[0][0] if rows else None


async def with_prefix(prefix: str) -> dict[str, str]:
    """Every key that starts with `prefix`, with its value.

    The prefix is matched literally, so `_` and `%` in a slug aren't wildcards.
    """
    index = get_index()
    rows = await asyncio.to_thread(
        index.read,
        f"SELECT key, value FROM {index.state_table} WHERE substr(key, 1, ?) = ?",
        [len(prefix), prefix],
    )
    return dict(rows)


async def put(key: str, value: str) -> None:
    """Set `key` to `value`, replacing what was there."""
    index = get_index()
    await asyncio.to_thread(
        index.write,
        lambda execute: execute(
            f"INSERT INTO {index.state_table} (key, value, updated_at) "
            "VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET "
            "value = excluded.value, updated_at = excluded.updated_at",
            [key, value, datetime.now(UTC).isoformat()],
        ),
    )


async def delete(key: str, value: str | None = None) -> bool:
    """Remove `key`; return whether this call removed it.

    With `value`, only while the key still holds that value, so of several
    callers settling the same row exactly one gets True.
    """
    index = get_index()
    sql = f"DELETE FROM {index.state_table} WHERE key = ?"
    params = [key]
    if value is not None:
        sql += " AND value = ?"
        params.append(value)
    removed = await asyncio.to_thread(
        index.write, lambda execute: execute(f"{sql} RETURNING key", params).fetchone()
    )
    return removed is not None


async def replace(key: str, old: str, new: str) -> bool:
    """Set `key` to `new` only while it holds `old`; return whether it did.

    Of several callers replacing the same value, exactly one gets True.
    """
    index = get_index()
    replaced = await asyncio.to_thread(
        index.write,
        lambda execute: execute(
            f"UPDATE {index.state_table} SET value = ?, updated_at = ? "
            "WHERE key = ? AND value = ? RETURNING key",
            [new, datetime.now(UTC).isoformat(), key, old],
        ).fetchone(),
    )
    return replaced is not None
