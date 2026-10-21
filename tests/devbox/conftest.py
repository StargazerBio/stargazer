"""Fixtures for the devbox tier (`uv run --all-extras pytest -m devbox`).

These tests run on the local devbox, so they need it up, `devbox/setup.sh`
applied since it was created (with its steps for this machine's DNS; it also
starts the Postgres server that holds the asset index), and kubectl pointed
at it. The session points Flyte at the devbox, bundling code from the repo
root as SDK code does by default, and holds the store port-forward open
while runs upload their code and inputs. Runs carry the devbox storage
settings in their run context, so nothing needs exporting first.
"""

import asyncio
import importlib.util
from urllib.parse import urlsplit

import flyte
import pytest

from app import config
from app.init import init
from stargazer.config import PROJECT_ROOT
from stargazer.utils.index import PostgresIndex

_spec = importlib.util.spec_from_file_location(
    "devbox_dashboard", PROJECT_ROOT / "devbox" / "dashboard.py"
)
devbox_dashboard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(devbox_dashboard)

# Where a pod on the devbox stores assets: the bucket, the Postgres index,
# and the stand-in user who owns them.
STORAGE = {
    "STARGAZER_STORE_ROOT": devbox_dashboard.STORE_ROOT,
    "STARGAZER_INDEX_URL": devbox_dashboard.INDEX_URL,
    "STARGAZER_OWNER": devbox_dashboard.SUBJECT,
}

# The local end of the port-forward to the devbox's Postgres, clear of a
# Postgres this machine may run on 5432.
_INDEX_PORT = 15432


@pytest.fixture(scope="session", autouse=True)
def init_flyte_context():
    """Point Flyte at the devbox and hold the store port-forward open."""
    if config.TARGET != "devbox":
        pytest.fail("The devbox tier needs STARGAZER_TARGET=devbox")
    init(config.FLYTE_CONFIG, root_dir=PROJECT_ROOT)
    with devbox_dashboard.storage_port_forward():
        yield


@pytest.fixture(autouse=True)
def isolated_storage():
    """Replace the unit tier's per-test store: these tests store on the devbox."""


@pytest.fixture(scope="session")
def dashboard() -> str:
    """Deploy the dashboard for the stand-in user, as `devbox/dashboard.py` does.

    Returns its URL. Deployed once per session, so it runs the current source.
    """
    return devbox_dashboard.deploy()


@pytest.fixture(scope="session")
def index_query():
    """Query the devbox's Postgres index from this machine.

    Returns `query(filters)`, giving the matching rows. Each call opens its
    own port-forward, since a forward dies with the pod it reached.
    """
    url = urlsplit(devbox_dashboard.INDEX_URL)
    local = url._replace(
        netloc=f"{url.username}:{url.password}@127.0.0.1:{_INDEX_PORT}"
    ).geturl()

    def query(filters: dict) -> list[dict]:
        """Rows matching every filter, through a fresh port-forward."""
        with devbox_dashboard.port_forward(
            "stargazer", "svc/postgres", _INDEX_PORT, 5432
        ):
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
