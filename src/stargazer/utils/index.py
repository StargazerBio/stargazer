"""
### The asset index: SQLite, Postgres or Aurora DSQL.

The metadata half of asset storage: one row per asset, keyed by its CID, with
where the bytes live (`uri`), the original filename, and the asset's
keyvalues as a JSON object. `query()` matches every filter key exactly; a
list value matches any of its entries, in one query. `make_index` opens the
index a `STARGAZER_INDEX_URL` names.

Locally, `SqliteIndex` is the index itself. On the devbox it's a Postgres
server that the dashboard and every pod reach through `PostgresIndex`. On
Union it's the user's `DsqlIndex` table, which their dashboard and every pod
in their project reach directly. Beside each index table is a state table
(`state_table_name`) for the dashboard's own per-user state.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import asyncio
import json
import os
import random
import socket
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from urllib.parse import parse_qs, urlsplit

import boto3
import certifi
import psycopg

from stargazer.config import logger

T = TypeVar("T")

# The URL schemes `make_index` opens as a `PostgresIndex`, and as a `DsqlIndex`.
_POSTGRES_SCHEMES = ("postgresql://", "postgres://")
DSQL_SCHEME = "dsql://"

# Tries per write before a serialization failure is raised.
_WRITE_ATTEMPTS = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS {table} (
    cid        TEXT PRIMARY KEY,
    uri        TEXT NOT NULL,
    name       TEXT NOT NULL,
    keyvalues  {json} NOT NULL,
    created_at TEXT NOT NULL
)
"""

_COLUMNS = "cid, uri, name, keyvalues, created_at"

# The dashboard's own per-user state, beside the index table: one value per key.
_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS {table} (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def postgres_table_sql(table: str) -> str:
    """`CREATE TABLE IF NOT EXISTS` for an index table on Postgres or DSQL."""
    return _SCHEMA.format(table=table, json=PostgresIndex._JSON_TYPE)


def state_table_name(table: str) -> str:
    """The state table beside index table `table` (`assets.u_jane_state`)."""
    return f"{table}_state"


def state_table_sql(table: str) -> str:
    """`CREATE TABLE IF NOT EXISTS` for the state table beside index table `table`."""
    return _STATE_SCHEMA.format(table=state_table_name(table))


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


class SqlIndex:
    """The index's five calls, written once in SQL that SQLite and Postgres share.

    Subclasses give what the engines spell differently: the JSON column type,
    one keyvalue's lookup and the merge (each with a `?` parameter), and how
    statements run, and set `table`. Statements use `?` placeholders
    throughout. `write` and `read` are public so the dashboard can keep its
    own rows in `state_table`, the table beside `table`. Writes are
    acknowledged only after they commit, so a downstream task always sees its
    upstream task's rows, and a merge is one statement, so concurrent merges
    each land.
    """

    table: str
    _JSON_TYPE: str
    _KEYVALUE: str
    _MERGE: str

    @property
    def state_table(self) -> str:
        """The dashboard's per-user state table, beside the index table."""
        return state_table_name(self.table)

    def _key(self, key: str) -> str:
        """The `_KEYVALUE` parameter that names `key`."""
        raise NotImplementedError

    def write(self, work: Callable[[Callable], T]) -> T:
        """Run `work(execute)` as one committed transaction."""
        raise NotImplementedError

    def read(self, sql: str, params: list) -> list[tuple]:
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
                f"SELECT keyvalues FROM {self.table} WHERE cid = ?", [cid]
            ).fetchone()
            if existing is not None:
                changed = _changed_keys(_decode(existing[0]), keyvalues)
                if changed:
                    logger.warning(
                        f"Asset {cid} re-uploaded with different metadata; "
                        f"replacing keys {changed}"
                    )
            return execute(
                f"INSERT INTO {self.table} ({_COLUMNS}) "
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

        return _row(self.write(work))

    def _merge_sync(self, cid: str, patch: dict[str, str]) -> dict:
        """Merge keyvalues onto a row in one statement."""
        stored = self.write(
            lambda execute: execute(
                f"UPDATE {self.table} SET keyvalues = {self._MERGE} WHERE cid = ? "
                f"RETURNING {_COLUMNS}",
                [json.dumps(patch), cid],
            ).fetchone()
        )
        if stored is None:
            raise ValueError(f"No index row for cid {cid}")
        return _row(stored)

    def _delete_sync(self, cid: str) -> None:
        """Remove a row."""
        self.write(
            lambda execute: execute(f"DELETE FROM {self.table} WHERE cid = ?", [cid])
        )

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
            self.read,
            f"SELECT {_COLUMNS} FROM {self.table} WHERE {where} "
            "ORDER BY created_at DESC",
            params,
        )
        return [_row(r) for r in rows]

    async def get(self, cid: str) -> dict | None:
        """One row by CID, or None."""
        rows = await asyncio.to_thread(
            self.read, f"SELECT {_COLUMNS} FROM {self.table} WHERE cid = ?", [cid]
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


class SqliteIndex(SqlIndex):
    """Asset metadata index in one SQLite file.

    Writes go through one connection behind a `threading.Lock`, taken inside
    the worker thread rather than an `asyncio.Lock` so one index can serve
    callers on different event loops; WAL mode lets reads run alongside a
    write.

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
        self.table = "assets"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._writer = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._writer.execute("PRAGMA journal_mode=WAL")
        self._writer.execute(_SCHEMA.format(table=self.table, json=self._JSON_TYPE))
        self._writer.execute(state_table_sql(self.table))
        self._writer.commit()

    def _key(self, key: str) -> str:
        """A JSON path to `key`, quoted so any key name is one path step."""
        return '$."' + key.replace('"', '\\"') + '"'

    def write(self, work: Callable[[Callable], T]) -> T:
        """Run `work` on the one writer connection, under the write lock."""
        with self._lock:
            try:
                result = work(self._writer.execute)
                self._writer.commit()
            except BaseException:
                self._writer.rollback()
                raise
        return result

    def read(self, sql: str, params: list) -> list[tuple]:
        """Run a read on its own connection (WAL readers never wait on the writer)."""
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()


class PostgresIndex(SqlIndex):
    """Asset metadata index in a Postgres database, keyvalues as `jsonb`.

    Each call opens its own connection, so concurrent writers are serialized
    by Postgres's row locks rather than a lock here. A write refused with a
    serialization failure is rerun whole, with jittered backoff.

    Usage:
        index = PostgresIndex("postgresql://user:pass@host:5432/db")
        rows = await index.query({"companion_of": cid})
    """

    _JSON_TYPE = "JSONB"
    _KEYVALUE = "(keyvalues ->> CAST(? AS TEXT))"
    _MERGE = "keyvalues || CAST(? AS JSONB)"

    def __init__(self, url: str, table: str = "assets"):
        """Connect to `url` and create the index and state tables if they're missing.

        Args:
            url: A `postgresql://` connection URL
            table: The table, schema-qualified if it isn't in the search path
        """
        self.url = url
        self.table = table
        with self._connect(autocommit=True) as conn:
            conn.execute(postgres_table_sql(table))
            conn.execute(state_table_sql(table))

    def _connect(self, autocommit: bool) -> psycopg.Connection:
        """A new connection to the database."""
        return psycopg.connect(self.url, autocommit=autocommit)

    def _key(self, key: str) -> str:
        """`->>` takes the key name itself."""
        return key

    def write(self, work: Callable[[Callable], T]) -> T:
        """Run `work` in one transaction on a new connection, rerun on conflict.

        DSQL refuses a write that conflicts with a concurrent one instead of
        making it wait, and Postgres does the same under serializable
        isolation, both with SQLSTATE 40001, at a statement or at commit.
        """
        delay = 0.02
        for _ in range(_WRITE_ATTEMPTS - 1):
            try:
                return self._transaction(work)
            except psycopg.errors.SerializationFailure:
                time.sleep(random.uniform(0, delay))
                delay = min(delay * 2, 1.0)
        return self._transaction(work)

    def _transaction(self, work: Callable[[Callable], T]) -> T:
        """Run `work` in one transaction on a new connection."""
        with self._connect(autocommit=False) as conn:
            return work(lambda sql, params: conn.execute(_pg(sql), params))

    def read(self, sql: str, params: list) -> list[tuple]:
        """Run a read on a new connection."""
        with self._connect(autocommit=True) as conn:
            return conn.execute(_pg(sql), params).fetchall()


class DsqlIndex(PostgresIndex):
    """A user's asset index table on Aurora DSQL, reached as their own login.

    The URL names the cluster endpoint, the user's database role, their
    table and the IAM role mapped to that database role:
    `dsql://u_jane@<id>.dsql.us-west-2.on.aws/assets.u_jane?role_arn=<arn>`.
    The index and state tables, the database role and the IAM role are made
    by onboarding; the database role can't create anything, so this never
    runs DDL.

    Each call connects afresh, so DSQL ending a connection after an hour
    never reaches a caller. The IAM role's credentials and the auth token
    are cached for the process; the token is signed locally, so the only
    remote calls per connection are STS when the credentials near expiry
    and the connection itself.

    Usage:
        index = DsqlIndex(os.environ["STARGAZER_INDEX_URL"])
        rows = await index.query({"companion_of": cid})
    """

    # Refresh the IAM role's credentials this long before they expire, and
    # sign a new token after this long (DSQL tokens last 15 minutes).
    _CREDENTIALS_MARGIN = 300
    _TOKEN_LIFETIME = 600

    def __init__(self, url: str):
        """Read the cluster, login, table and IAM role from `url`; no connection.

        Args:
            url: A `dsql://` index URL (see the class docstring)

        Raises:
            ValueError: when `url` has no login, table or `role_arn`, or its
                host isn't a DSQL endpoint
        """
        parts = urlsplit(url)
        host = parts.hostname or ""
        labels = host.split(".")
        role_arn = parse_qs(parts.query).get("role_arn", [""])[0]
        table = parts.path.lstrip("/")
        if len(labels) < 3 or labels[1] != "dsql":
            raise ValueError(f"Not a DSQL endpoint (<id>.dsql.<region>...): {host}")
        if not (parts.username and table and role_arn):
            raise ValueError(
                "A DSQL index URL names its login, table and IAM role: "
                "dsql://<login>@<endpoint>/<schema>.<table>?role_arn=<arn>"
            )
        self.endpoint = host
        self.region = labels[2]
        self.user = parts.username
        self.table = table
        self.role_arn = role_arn
        self._lock = threading.Lock()
        self._dsql = None
        self._credentials_expire = 0.0
        self._token = ""
        self._token_expires = 0.0

    def _password(self) -> str:
        """A DSQL auth token for `user`, signed with the IAM role's credentials.

        The role is assumed with the pod's own service-account token, which
        STS accepts for the role only from the user's namespace.
        """
        with self._lock:
            now = time.time()
            if now >= self._credentials_expire:
                web_token = Path(os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]).read_text()
                creds = boto3.client(
                    "sts", region_name=self.region
                ).assume_role_with_web_identity(
                    RoleArn=self.role_arn,
                    RoleSessionName="stargazer-index",
                    WebIdentityToken=web_token,
                )["Credentials"]
                self._dsql = boto3.Session(
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                ).client("dsql", region_name=self.region)
                self._credentials_expire = (
                    creds["Expiration"].timestamp() - self._CREDENTIALS_MARGIN
                )
                self._token_expires = 0.0
            if now >= self._token_expires:
                self._token = self._dsql.generate_db_connect_auth_token(
                    self.endpoint, self.region
                )
                self._token_expires = min(
                    now + self._TOKEN_LIFETIME, self._credentials_expire
                )
            return self._token

    def _connect(self, autocommit: bool) -> psycopg.Connection:
        """A verified TLS connection to the cluster as `user`, over IPv4.

        Task pods have no IPv6 route and the endpoint resolves to both, so
        leaving the choice to libpq costs a failed IPv6 attempt on every
        connect (measured on the tenant). certifi's bundle carries the
        Amazon root CA that signs the cluster's certificate.
        """
        ipv4 = socket.getaddrinfo(
            self.endpoint, 5432, socket.AF_INET, socket.SOCK_STREAM
        )[0][4][0]
        ssl = {"sslmode": "verify-full", "sslrootcert": certifi.where()}
        if psycopg.pq.version() >= 170000:
            ssl["sslnegotiation"] = "direct"
        return psycopg.connect(
            host=self.endpoint,
            hostaddr=ipv4,
            port=5432,
            dbname="postgres",
            user=self.user,
            password=self._password(),
            connect_timeout=15,
            autocommit=autocommit,
            **ssl,
        )


def _pg(sql: str) -> str:
    """`?` placeholders as psycopg's `%s`."""
    return sql.replace("?", "%s")


def make_index(url: str) -> SqlIndex:
    """The index named by `STARGAZER_INDEX_URL`.

    A `postgresql://` (or `postgres://`) URL is a Postgres database; a
    `dsql://` URL is a user's table on Aurora DSQL (see `DsqlIndex`);
    anything else is a SQLite file path (a `sqlite://` prefix is accepted and
    stripped, `~` is expanded).
    """
    if url.startswith(DSQL_SCHEME):
        return DsqlIndex(url)
    if url.startswith(_POSTGRES_SCHEMES):
        return PostgresIndex(url)
    return SqliteIndex(Path(url.removeprefix("sqlite://")).expanduser())
