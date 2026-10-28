"""Fixtures for the devbox tier (`uv run --all-extras pytest -m devbox`).

These tests run on the local devbox, so they need it up, infra's devbox setup
applied since it was created (it also starts the Postgres server that holds
the asset index), and kubectl pointed at it. The session points Flyte at the
devbox with `.flyte/config.yaml`, whose `image.registry` is the devbox's
registry, bundling code from the repo root as SDK code does by default, and
holds the store port-forward open while runs upload their code and inputs.
Runs carry the devbox storage settings in their run context, so nothing needs
exporting first.
"""

import asyncio
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from urllib.parse import urlsplit

import flyte
import pytest

from stargazer.config import PROJECT_ROOT
from stargazer.utils.index import PostgresIndex

# Where a pod on the devbox stores assets: the devbox's bucket, its Postgres
# index (infra's devbox setup runs the server), and a stand-in owner.
STORAGE = {
    "STARGAZER_STORE_ROOT": "s3://flyte-data/stargazer",
    "STARGAZER_INDEX_URL": (
        "postgresql://stargazer:stargazer@"
        "postgres.stargazer.svc.cluster.local:5432/stargazer"
    ),
    "STARGAZER_OWNER": "devbox-user",
}

# The local end of the port-forward to the devbox's Postgres, clear of a
# Postgres this machine may run on 5432.
_INDEX_PORT = 15432


def _port_open(port: int) -> bool:
    """Whether something already listens on localhost:`port`."""
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def port_forward(namespace: str, service: str, local: int, remote: int):
    """Hold `localhost:<local> → <service>:<remote>` open; reuse one already open."""
    if _port_open(local):
        yield
        return
    proc = subprocess.Popen(
        ["kubectl", "port-forward", "-n", namespace, service, f"{local}:{remote}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            if _port_open(local):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(
                f"kubectl port-forward to {namespace}/{service} didn't open"
            )
        yield
    finally:
        proc.terminate()


@pytest.fixture(scope="session", autouse=True)
def init_flyte_context():
    """Point Flyte at the devbox and hold the store port-forward open.

    Uploads go to the in-cluster signed-URL host, which the forward of the
    object store (rustfs) answers on this machine.
    """
    # Buildx attaches a provenance attestation by default, which turns even a
    # one-platform push into an index; an arm64 node finds no arm64 entry in
    # it and refuses the pull. A plain image pulls and runs under emulation.
    os.environ.setdefault("FLYTE_DOCKER_BUILD_EXTRA_ARGS", "--provenance=false")
    flyte.init_from_config(
        PROJECT_ROOT / ".flyte" / "config.yaml", root_dir=PROJECT_ROOT
    )
    with port_forward("flyte", "svc/rustfs-svc", 9000, 9000):
        yield


@pytest.fixture(autouse=True)
def isolated_storage():
    """Replace the unit tier's per-test store: these tests store on the devbox."""


@pytest.fixture(scope="session")
def index_query():
    """Query the devbox's Postgres index from this machine.

    Returns `query(filters)`, giving the matching rows. Each call opens its
    own port-forward, since a forward dies with the pod it reached.
    """
    url = urlsplit(STORAGE["STARGAZER_INDEX_URL"])
    local = url._replace(
        netloc=f"{url.username}:{url.password}@127.0.0.1:{_INDEX_PORT}"
    ).geturl()

    def query(filters: dict) -> list[dict]:
        """Rows matching every filter, through a fresh port-forward."""
        with port_forward("stargazer", "svc/postgres", _INDEX_PORT, 5432):
            return asyncio.run(PostgresIndex(local).query(filters))

    return query


@pytest.fixture(scope="session")
def devbox_run():
    """Run a task on the devbox with the devbox storage settings.

    Returns the finished run. Prints its URL, which `-rP` shows, and raises
    when the run failed.
    """

    def run(task, **inputs):
        """Run `task`, wait for it, and return the run."""
        started = flyte.with_runcontext(env_vars=STORAGE).run(task, **inputs)
        print(f"{task.name}: {started.url}")
        started.wait()
        started.raise_for_status()
        return started

    return run
