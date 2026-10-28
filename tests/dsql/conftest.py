"""Fixtures for the dsql tier (`uv run --all-extras pytest -m dsql`).

The index tests run against the real cluster `STARGAZER_DSQL_CLUSTER_ARN`
names (infra's `tenant.env`), as its admin with your AWS session: a run
without them fails rather than skipping. They cover what Postgres can't: the
connection's IAM auth and TLS, and the write retry under DSQL's own
optimistic concurrency. Each session works in its own schema, made and
dropped here, so it never touches a user's tables.
"""

import os
import uuid

import boto3
import certifi
import psycopg
import pytest

from app import assets as assets_mod
from app.deploy import dsql_cluster
from stargazer.utils.index import DsqlIndex, postgres_table_sql, state_table_sql


def _admin(endpoint: str, region: str) -> psycopg.Connection:
    """An autocommit connection to the cluster as its admin, for the DDL."""
    token = (
        boto3.Session(region_name=region)
        .client("dsql")
        .generate_db_connect_admin_auth_token(endpoint, region)
    )
    return psycopg.connect(
        host=endpoint,
        dbname="postgres",
        user="admin",
        password=token,
        sslmode="verify-full",
        sslrootcert=certifi.where(),
        autocommit=True,
    )


@pytest.fixture(scope="session")
def dsql_table():
    """`(endpoint, table)`: an index table and its state table in a new schema.

    DSQL runs one DDL statement per transaction, hence autocommit.
    """
    cluster_arn = os.environ.get("STARGAZER_DSQL_CLUSTER_ARN")
    if not cluster_arn:
        pytest.fail(
            "The dsql tier needs STARGAZER_DSQL_CLUSTER_ARN and an AWS session: "
            "run it with --env-file <infra>/tenant.env"
        )
    region, _, endpoint = dsql_cluster(cluster_arn)
    schema = f"stargazer_test_{uuid.uuid4().hex[:8]}"
    table = f"{schema}.assets"
    with _admin(endpoint, region) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")
        conn.execute(postgres_table_sql(table))
        conn.execute(state_table_sql(table))
    try:
        yield endpoint, table
    finally:
        with _admin(endpoint, region) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"DROP TABLE IF EXISTS {table}_state")
            conn.execute(f"DROP SCHEMA IF EXISTS {schema}")


@pytest.fixture
def index(dsql_table):
    """The test schema's index, emptied, reached as the admin through `DsqlIndex`."""
    endpoint, table = dsql_table
    index = DsqlIndex(f"dsql://admin@{endpoint}/{table}")
    index.write(lambda execute: execute(f"DELETE FROM {table}", []))
    index.write(lambda execute: execute(f"DELETE FROM {index.state_table}", []))
    return index


@pytest.fixture
def state_index(index, monkeypatch):
    """The dashboard's index, for `app.user_state`, on the test schema."""
    monkeypatch.setattr(assets_mod, "_index", index)
    return index
