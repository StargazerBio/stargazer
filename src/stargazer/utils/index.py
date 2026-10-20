"""
### The asset index: SQLite or Postgres, or the user's dashboard over HTTP.

The metadata half of asset storage: one row per asset, keyed by its CID, with
where the bytes live (`uri`), the original filename, and the asset's
keyvalues as a JSON object. `query()` keeps the semantics storage has always
had — every filter key must match exactly — and adds list values that match
any of their entries in a single query.

`SqliteIndex` and `PostgresIndex` share one implementation of the calls, in
SQL both engines accept; each says only how it spells a JSON column, a
keyvalue lookup and a merge, and how it runs a statement. Writes are
acknowledged only after they commit, so a downstream task always sees its
upstream task's rows, and a merge is one statement, so concurrent merges
each land.

SQLite serializes writes through one connection behind a `threading.Lock`,
taken inside the worker thread rather than an `asyncio.Lock` so one index
can serve callers on different event loops; WAL mode lets reads run
alongside a write. Postgres opens a connection per call and leaves
concurrency to the database.

Re-upserting a CID with different keyvalues replaces them and logs a WARNING:
the same bytes recorded with new metadata is allowed, but should be visible.

Locally, `SqliteIndex` is the index itself. On Union the user's dashboard
owns a SQLite file and serves it over HTTP; pods reach it through
`HttpIndex`, which makes the same calls.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import asyncio
import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import httpx
import psycopg

from stargazer.config import logger

T = TypeVar("T")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    cid        TEXT PRIMARY KEY,
    uri        TEXT NOT NULL,
    name       TEXT NOT NULL,
    keyvalues  {json} NOT NULL,
    created_at TEXT NOT NULL
)
"""

_COLUMNS = "cid, uri, name, keyvalues, created_at"


def _decode(keyvalues: str | dict) -> dict:
    """Keyvalues as a dict: SQLite returns JSON text, Postgres a parsed object."""
    return keyvalues if isinstance(keyvalues, dict) else json.loads(keyvalues)


def _row(values: tuple) -> dict:
    """A result tuple as a record dict with parsed keyvalues."""
    cid, uri, name, keyvalues, created_at = values
    return {
        "cid": cid,
        "uri": uri,
        "name": name,
        "keyvalues": _decode(keyvalues),
        "created_at": created_at,
    }


def _changed_keys(old: dict, new: dict) -> list[str]:
    """Keys added, removed, or given a different value."""
    return sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))


class _SqlIndex:
    """The index's five calls, written once in SQL that SQLite and Postgres share.

    Subclasses give what the engines spell differently: the JSON column type,
    one keyvalue's lookup and the merge (each with a `?` parameter), and how
    statements run. Statements use `?` placeholders throughout.
    """

    _JSON_TYPE: str
    _KEYVALUE: str
    _MERGE: str

    def _key(self, key: str) -> str:
        """The `_KEYVALUE` parameter that names `key`."""
        raise NotImplementedError

    def _write(self, work: Callable[[Callable], T]) -> T:
        """Run `work(execute)` as one committed transaction."""
        raise NotImplementedError

    def _read(self, sql: str, params: list) -> list[tuple]:
        """Rows from one read-only statement."""
        raise NotImplementedError

    def _where(self, filters: dict) -> tuple[str, list]:
        """SQL WHERE clause and parameters for exact-match keyvalue filters."""
        clauses: list[str] = []
        params: list = []
        for key, value in filters.items():
            if isinstance(value, list):
                if not value:
                    return "FALSE", []
                marks = ", ".join("?" * len(value))
                clauses.append(f"{self._KEYVALUE} IN ({marks})")
                params += [self._key(key), *value]
            else:
                clauses.append(f"{self._KEYVALUE} = ?")
                params += [self._key(key), value]
        return (" AND ".join(clauses) or "TRUE"), params

    def _upsert_sync(self, record: dict) -> dict:
        """Insert or replace one row, warning when its keyvalues change."""
        cid = record["cid"]
        keyvalues = dict(record["keyvalues"])

        def work(execute):
            """Read the old keyvalues and write the row, in one transaction."""
            existing = execute(
                "SELECT keyvalues FROM assets WHERE cid = ?", [cid]
            ).fetchone()
            if existing is not None:
                changed = _changed_keys(_decode(existing[0]), keyvalues)
                if changed:
                    logger.warning(
                        f"Asset {cid} re-uploaded with different metadata; "
                        f"replacing keys {changed}"
                    )
            return execute(
                f"INSERT INTO assets ({_COLUMNS}) "
                f"VALUES (?, ?, ?, CAST(? AS {self._JSON_TYPE}), ?) "
                "ON CONFLICT (cid) DO UPDATE SET uri = excluded.uri, "
                "name = excluded.name, keyvalues = excluded.keyvalues "
                f"RETURNING {_COLUMNS}",
                [
                    cid,
                    record["uri"],
                    record["name"],
                    json.dumps(keyvalues),
                    datetime.now(UTC).isoformat(),
                ],
            ).fetchone()

        return _row(self._write(work))

    def _merge_sync(self, cid: str, patch: dict[str, str]) -> dict:
        """Merge keyvalues onto a row in one statement."""
        stored = self._write(
            lambda execute: execute(
                f"UPDATE assets SET keyvalues = {self._MERGE} WHERE cid = ? "
                f"RETURNING {_COLUMNS}",
                [json.dumps(patch), cid],
            ).fetchone()
        )
        if stored is None:
            raise ValueError(f"No index row for cid {cid}")
        return _row(stored)

    def _delete_sync(self, cid: str) -> None:
        """Remove a row."""
        self._write(lambda execute: execute("DELETE FROM assets WHERE cid = ?", [cid]))

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
        where, params = self._where(filters)
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


class SqliteIndex(_SqlIndex):
    """Asset metadata index in one SQLite file.

    Usage:
        index = SqliteIndex(Path("~/.stargazer/index.db").expanduser())
        await index.upsert({"cid": cid, "uri": uri, "name": name, "keyvalues": kv})
        rows = await index.query({"asset": "alignment", "sample_id": ["S1", "S2"]})
    """

    _JSON_TYPE = "TEXT"
    _KEYVALUE = "json_extract(keyvalues, ?)"
    _MERGE = "json_patch(keyvalues, ?)"

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
        self._writer.execute(_SCHEMA.format(json=self._JSON_TYPE))
        self._writer.commit()

    def _key(self, key: str) -> str:
        """A JSON path to `key`, quoted so any key name is one path step."""
        return '$."' + key.replace('"', '\\"') + '"'

    def _write(self, work: Callable[[Callable], T]) -> T:
        """Run `work` on the one writer connection, under the write lock."""
        with self._lock:
            try:
                result = work(self._writer.execute)
                self._writer.commit()
            except BaseException:
                self._writer.rollback()
                raise
        return result

    def _read(self, sql: str, params: list) -> list[tuple]:
        """Run a read on its own connection (WAL readers never wait on the writer)."""
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()


class PostgresIndex(_SqlIndex):
    """Asset metadata index in a Postgres database, keyvalues as `jsonb`.

    Each call opens its own connection, so concurrent writers are serialized
    by Postgres's row locks rather than a lock here.

    Usage:
        index = PostgresIndex("postgresql://user:pass@host:5432/db")
        rows = await index.query({"companion_of": cid})
    """

    _JSON_TYPE = "JSONB"
    _KEYVALUE = "(keyvalues ->> CAST(? AS TEXT))"
    _MERGE = "keyvalues || CAST(? AS JSONB)"

    def __init__(self, url: str):
        """Connect to `url` and create the assets table if it's missing.

        Args:
            url: A `postgresql://` connection URL
        """
        self.url = url
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(_SCHEMA.format(json=self._JSON_TYPE))

    def _key(self, key: str) -> str:
        """`->>` takes the key name itself."""
        return key

    def _write(self, work: Callable[[Callable], T]) -> T:
        """Run `work` in one transaction on a new connection."""
        with psycopg.connect(self.url) as conn:
            return work(lambda sql, params: conn.execute(_pg(sql), params))

    def _read(self, sql: str, params: list) -> list[tuple]:
        """Run a read on a new connection."""
        with psycopg.connect(self.url, autocommit=True) as conn:
            return conn.execute(_pg(sql), params).fetchall()


def _pg(sql: str) -> str:
    """`?` placeholders as psycopg's `%s`."""
    return sql.replace("?", "%s")


class HttpIndex:
    """The asset index served by a user's dashboard, over HTTP.

    The same calls as `SqliteIndex`, sent to the dashboard's `/index` routes
    (`app/index_api.py`), which run them on the dashboard's own SQLite file.
    Task and notebook pods reach the dashboard at its in-cluster address.
    Connection errors and 5xx responses are retried with backoff (a dashboard
    that has scaled to zero answers once it's up); if every attempt fails the
    call raises, so a task whose write didn't land fails rather than losing
    the row quietly.

    Usage:
        index = HttpIndex("http://dashboard.u-jane-development.svc.cluster.local")
        await index.upsert({"cid": cid, "uri": uri, "name": name, "keyvalues": kv})
    """

    def __init__(
        self,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        attempts: int = 5,
        backoff: float = 0.5,
    ):
        """Point at a dashboard.

        Args:
            base_url: The dashboard's base URL
            transport: An httpx transport to use instead of the network (tests)
            attempts: Tries per call before giving up
            backoff: Seconds before the first retry, doubling each time
        """
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self._attempts = attempts
        self._backoff = backoff

    async def _send(self, method: str, path: str, body: dict | None = None):
        """One call to the dashboard, retried on connection errors and 5xx."""
        delay = self._backoff
        for attempt in range(1, self._attempts + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url, transport=self._transport, timeout=120
                ) as client:
                    response = await client.request(method, path, json=body)
                if response.status_code < 500:
                    return response
                response.raise_for_status()
            except (httpx.TransportError, httpx.HTTPStatusError):
                if attempt == self._attempts:
                    raise
            logger.warning(
                f"Index {method} {path} failed (attempt {attempt}/{self._attempts}); "
                f"retrying in {delay}s"
            )
            await asyncio.sleep(delay)
            delay *= 2
        raise AssertionError("unreachable")

    async def upsert(self, record: dict) -> dict:
        """Insert a row, or replace an existing row (see `SqliteIndex.upsert`)."""
        response = await self._send("POST", "/index/assets", record)
        response.raise_for_status()
        return response.json()

    async def query(self, filters: dict) -> list[dict]:
        """Rows matching every filter; a list value matches any of its entries."""
        response = await self._send("POST", "/index/query", {"filters": filters})
        response.raise_for_status()
        return response.json()

    async def get(self, cid: str) -> dict | None:
        """One row by CID, or None."""
        response = await self._send("GET", f"/index/assets/{cid}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def merge(self, cid: str, patch: dict[str, str]) -> dict:
        """Merge keyvalues onto a row.

        Raises:
            ValueError: when no row exists for `cid`
        """
        response = await self._send(
            "PATCH", f"/index/assets/{cid}", {"keyvalues": patch}
        )
        if response.status_code == 404:
            raise ValueError(f"No index row for cid {cid}")
        response.raise_for_status()
        return response.json()

    async def delete(self, cid: str) -> None:
        """Remove a row. Deleting a missing row is a no-op."""
        response = await self._send("DELETE", f"/index/assets/{cid}")
        response.raise_for_status()
