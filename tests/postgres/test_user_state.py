"""The state tests in tests/unit/test_user_state.py, on Postgres and as a DSQL login.

As a login, the state table already exists, made by the admin beside the
index table, and the login holds only row privileges on the two tables.
"""

import psycopg
import pytest
from unit.test_user_state import (  # noqa: F401 — pytest collects the imported tests
    test_a_set_value_reads_back,
    test_concurrent_conditional_deletes_take_it_once,
    test_delete_removes_the_key,
    test_delete_with_a_value_only_takes_that_value,
    test_put_replaces_the_value,
    test_with_prefix_takes_only_the_prefix,
)

from app import assets as assets_mod
from stargazer.utils.index import DsqlIndex, PostgresIndex


def _postgres(postgres_url):
    """The index's own tables on the server, as `PostgresIndex` makes them."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS assets, assets_state")
    return PostgresIndex(postgres_url)


def _dsql_login(postgres_url):
    """`assets.u_probe` and its state table, reached as the `u_probe` login only."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS assets CASCADE")
        conn.execute("DROP ROLE IF EXISTS u_probe")
        conn.execute("CREATE SCHEMA assets")
    PostgresIndex(postgres_url, table="assets.u_probe")
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("CREATE ROLE u_probe WITH LOGIN PASSWORD 'probe'")
        conn.execute("GRANT USAGE ON SCHEMA assets TO u_probe")
        conn.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE "
            "ON assets.u_probe, assets.u_probe_state TO u_probe"
        )
    index = DsqlIndex(
        "dsql://u_probe@abc123.dsql.us-west-2.on.aws/assets.u_probe"
        "?role_arn=arn:aws:iam::111122223333:role/stargazer-index-u-probe"
    )
    as_login = postgres_url.replace("postgres:stargazer@", "u_probe:probe@")
    index._connect = lambda autocommit: psycopg.connect(as_login, autocommit=autocommit)
    return index


@pytest.fixture(params=[_postgres, _dsql_login], ids=["postgres", "dsql-login"])
def state_index(request, postgres_url, monkeypatch):
    """The dashboard's index on Postgres, then as a user's DSQL login."""
    index = request.param(postgres_url)
    monkeypatch.setattr(assets_mod, "_index", index)
    return index
