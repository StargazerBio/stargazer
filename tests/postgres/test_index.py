"""The index contract (tests/utils/test_index.py), run against Postgres.

`test_read_during_a_held_write` stays with SQLite: it holds SQLite's file lock.
"""

import asyncio

import psycopg
from utils.test_index import (  # noqa: F401 — pytest collects the imported class
    TestIndexContract,
    _record,
)

from stargazer.utils.index import PostgresIndex, make_index


def test_make_index_picks_postgres_for_a_postgres_url(postgres_url):
    """A `postgresql://` STARGAZER_INDEX_URL gives a Postgres index."""
    assert type(make_index(postgres_url)) is PostgresIndex


async def test_serialization_failures_are_retried(postgres_url):
    """Under serializable isolation, as on DSQL, concurrent merges each land.

    Postgres refuses all but one concurrent update of a row with SQLSTATE
    40001 here, the error DSQL gives a conflicting write.
    """
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS assets")
    index = PostgresIndex(
        postgres_url + "?options=-c%20default_transaction_isolation%3Dserializable"
    )
    await index.upsert(_record("bafyA", asset="alignment"))

    await asyncio.gather(*(index.merge("bafyA", {f"k{i}": str(i)}) for i in range(20)))

    [row] = await index.query({})
    assert {f"k{i}": str(i) for i in range(20)}.items() <= row["keyvalues"].items()
