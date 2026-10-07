"""
### SQLite asset index.

The metadata half of asset storage: one row per asset, keyed by its CID, with
where the bytes live (`uri`), the original filename, and the asset's
keyvalues as a JSON object. `query()` keeps the semantics storage has always
had — every filter key must match exactly — and adds list values that match
any of their entries in a single query.

Writes are serialized through one connection behind a lock and acknowledged
only after they commit, so a downstream task always sees its upstream task's
rows. The lock is a `threading.Lock` taken inside the worker thread rather
than an `asyncio.Lock`, so one index can serve callers on different event
loops. WAL mode lets reads run alongside a write without waiting for it.

Re-upserting a CID with different keyvalues replaces them and logs a WARNING:
the same bytes recorded with new metadata is allowed, but should be visible.

On a laptop this is the index itself; on Union the user's dashboard owns the
file and serves it over HTTP.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import asyncio
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from stargazer.config import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    cid        TEXT PRIMARY KEY,
    uri        TEXT NOT NULL,
    name       TEXT NOT NULL,
    keyvalues  TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_COLUMNS = "cid, uri, name, keyvalues, created_at"


def _row(values: tuple) -> dict:
    """A result tuple as a record dict with parsed keyvalues."""
    cid, uri, name, keyvalues, created_at = values
    return {
        "cid": cid,
        "uri": uri,
        "name": name,
        "keyvalues": json.loads(keyvalues),
        "created_at": created_at,
    }


def _where(filters: dict) -> tuple[str, list]:
    """SQL WHERE clause and parameters for exact-match keyvalue filters."""
    clauses: list[str] = []
    params: list = []
    for key, value in filters.items():
        json_path = '$."' + key.replace('"', '\\"') + '"'
        if isinstance(value, list):
            if not value:
                return "0", []
            marks = ", ".join("?" * len(value))
            clauses.append(f"json_extract(keyvalues, ?) IN ({marks})")
            params += [json_path, *value]
        else:
            clauses.append("json_extract(keyvalues, ?) = ?")
            params += [json_path, value]
    return (" AND ".join(clauses) or "1"), params


def _changed_keys(old: dict, new: dict) -> list[str]:
    """Keys added, removed, or given a different value."""
    return sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))


class SqliteIndex:
    """Asset metadata index in one SQLite file.

    Usage:
        index = SqliteIndex(Path("~/.stargazer/index.db").expanduser())
        await index.upsert({"cid": cid, "uri": uri, "name": name, "keyvalues": kv})
        rows = await index.query({"asset": "alignment", "sample_id": ["S1", "S2"]})
    """

    def __init__(self, path: Path):
        """Open (or create) the index at `path`, in WAL mode.

        Args:
            path: The SQLite file; its parent directory is created if missing
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._writer = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._writer.execute("PRAGMA journal_mode=WAL")
        self._writer.execute(_SCHEMA)
        self._writer.commit()

    def _read(self, sql: str, params: list) -> list[tuple]:
        """Run a read on its own connection (WAL readers never wait on the writer)."""
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _upsert_sync(self, record: dict) -> dict:
        """Insert or replace one row under the write lock."""
        cid = record["cid"]
        keyvalues = dict(record["keyvalues"])
        with self._lock:
            existing = self._writer.execute(
                "SELECT keyvalues FROM assets WHERE cid = ?", (cid,)
            ).fetchone()
            if existing is not None:
                changed = _changed_keys(json.loads(existing[0]), keyvalues)
                if changed:
                    logger.warning(
                        f"Asset {cid} re-uploaded with different metadata; "
                        f"replacing keys {changed}"
                    )
            self._writer.execute(
                f"INSERT INTO assets ({_COLUMNS}) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(cid) DO UPDATE SET uri = excluded.uri, "
                "name = excluded.name, keyvalues = excluded.keyvalues",
                (
                    cid,
                    record["uri"],
                    record["name"],
                    json.dumps(keyvalues),
                    datetime.now(UTC).isoformat(),
                ),
            )
            self._writer.commit()
            stored = self._writer.execute(
                f"SELECT {_COLUMNS} FROM assets WHERE cid = ?", (cid,)
            ).fetchone()
        return _row(stored)

    def _merge_sync(self, cid: str, patch: dict[str, str]) -> dict:
        """Merge keyvalues onto a row under the write lock."""
        with self._lock:
            existing = self._writer.execute(
                "SELECT keyvalues FROM assets WHERE cid = ?", (cid,)
            ).fetchone()
            if existing is None:
                raise ValueError(f"No index row for cid {cid}")
            merged = {**json.loads(existing[0]), **patch}
            self._writer.execute(
                "UPDATE assets SET keyvalues = ? WHERE cid = ?",
                (json.dumps(merged), cid),
            )
            self._writer.commit()
            stored = self._writer.execute(
                f"SELECT {_COLUMNS} FROM assets WHERE cid = ?", (cid,)
            ).fetchone()
        return _row(stored)

    def _delete_sync(self, cid: str) -> None:
        """Remove a row under the write lock."""
        with self._lock:
            self._writer.execute("DELETE FROM assets WHERE cid = ?", (cid,))
            self._writer.commit()

    async def upsert(self, record: dict) -> dict:
        """Insert a row, or replace an existing row's uri, name and keyvalues.

        A different set of keyvalues for an existing CID logs a WARNING naming
        the keys that changed. `created_at` keeps its first value.

        Args:
            record: `cid`, `uri`, `name` and `keyvalues`

        Returns:
            The stored row
        """
        return await asyncio.to_thread(self._upsert_sync, record)

    async def query(self, filters: dict) -> list[dict]:
        """Rows matching every filter, newest first.

        Args:
            filters: Keyvalue filters; a list value matches any of its entries

        Returns:
            Matching rows: `cid`, `uri`, `name`, `keyvalues`, `created_at`
        """
        where, params = _where(filters)
        rows = await asyncio.to_thread(
            self._read,
            f"SELECT {_COLUMNS} FROM assets WHERE {where} ORDER BY created_at DESC",
            params,
        )
        return [_row(r) for r in rows]

    async def get(self, cid: str) -> dict | None:
        """One row by CID, or None."""
        rows = await asyncio.to_thread(
            self._read, f"SELECT {_COLUMNS} FROM assets WHERE cid = ?", [cid]
        )
        return _row(rows[0]) if rows else None

    async def merge(self, cid: str, patch: dict[str, str]) -> dict:
        """Merge keyvalues onto a row: supplied keys are set, others kept.

        Raises:
            ValueError: when no row exists for `cid`
        """
        return await asyncio.to_thread(self._merge_sync, cid, patch)

    async def delete(self, cid: str) -> None:
        """Remove a row. Deleting a missing row is a no-op."""
        await asyncio.to_thread(self._delete_sync, cid)
