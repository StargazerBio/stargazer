"""The index tests in tests/utils/test_index.py, run as a DSQL user's login.

DSQL itself only runs on the tenant, so these run `DsqlIndex`'s SQL on
Postgres the way DSQL is set up: the table already exists in the shared
`assets` schema, made by the admin, and the login holds only `USAGE` on the
schema and row privileges on its own table, so it can't create anything.
Its connection is swapped for a password login as that role.
"""

import psycopg
import pytest
from utils.test_index import (  # noqa: F401 — pytest collects the imported tests
    test_companion_lookup,
    test_concurrent_merges_keep_every_key,
    test_delete_is_idempotent,
    test_exact_match,
    test_list_filter_matches_any,
    test_merge_missing_row_raises,
    test_new_metadata_replaces_and_warns,
    test_round_trip,
    test_same_row_twice_is_one_row_without_warning,
    warnings,
)

from stargazer.utils.index import DsqlIndex, PostgresIndex


@pytest.fixture
def index(postgres_url):
    """A user's index: `assets.u_probe`, reached as the `u_probe` login only."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS assets CASCADE")
        conn.execute("DROP ROLE IF EXISTS u_probe")
        conn.execute("CREATE SCHEMA assets")
    PostgresIndex(postgres_url, table="assets.u_probe")
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("CREATE ROLE u_probe WITH LOGIN PASSWORD 'probe'")
        conn.execute("GRANT USAGE ON SCHEMA assets TO u_probe")
        conn.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON assets.u_probe TO u_probe"
        )
    index = DsqlIndex(
        "dsql://u_probe@abc123.dsql.us-west-2.on.aws/assets.u_probe"
        "?role_arn=arn:aws:iam::111122223333:role/stargazer-index-u-probe"
    )
    as_login = postgres_url.replace("postgres:stargazer@", "u_probe:probe@")
    index._connect = lambda autocommit: psycopg.connect(as_login, autocommit=autocommit)
    return index
