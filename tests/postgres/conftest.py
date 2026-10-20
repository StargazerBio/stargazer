"""Fixtures for the postgres tier (`uv run --all-extras pytest -m postgres`).

The index tests run against a throwaway Postgres 16 container, the version
Aurora DSQL is compatible with, started once per session with Docker. A run
without Docker fails rather than skipping.
"""

import shutil
import subprocess
import time

import psycopg
import pytest

from stargazer.utils.index import PostgresIndex

_IMAGE = "postgres:16-alpine"


@pytest.fixture(scope="session")
def postgres_url():
    """A Postgres server in a container for the session; removed afterwards."""
    if shutil.which("docker") is None:
        pytest.fail("The postgres tier needs Docker to start its Postgres server")
    container = subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "-e", "POSTGRES_PASSWORD=stargazer",
            "-p", "127.0.0.1::5432",
            _IMAGE,
        ],
        check=True, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip
    try:
        address = subprocess.run(
            ["docker", "port", container, "5432/tcp"],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()[0]  # fmt: skip
        url = f"postgresql://postgres:stargazer@{address}/postgres"
        # The image's entrypoint initializes on a socket-only server, then
        # restarts on TCP; the first TCP connection means it's ready.
        deadline = time.monotonic() + 60
        while True:
            try:
                psycopg.connect(url).close()
                break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        yield url
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container], check=False, capture_output=True
        )


@pytest.fixture
def index(postgres_url):
    """A fresh index: the assets table is dropped before each test."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS assets")
    return PostgresIndex(postgres_url)
