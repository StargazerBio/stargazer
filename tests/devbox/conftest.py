"""Fixtures for the devbox tier (`uv run --all-extras pytest -m devbox`).

These tests run on the local devbox, so they need it up, `cli/devbox-setup.sh`
applied since it was created (with its steps for this machine's DNS), and
kubectl pointed at it. The session points Flyte at the devbox, bundling code
from the repo root as SDK code does by default, and holds the store
port-forward open while runs upload their code and inputs. Runs carry the
devbox storage settings in their run context, so nothing needs exporting
first.
"""

import importlib.util

import flyte
import pytest

from app import config
from app.init import init
from stargazer.config import PROJECT_ROOT

_spec = importlib.util.spec_from_file_location(
    "devbox_dashboard", PROJECT_ROOT / "cli" / "devbox_dashboard.py"
)
devbox_dashboard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(devbox_dashboard)

# Where a pod on the devbox stores assets: the bucket, the dashboard's
# in-cluster address, and the stand-in user who owns them.
STORAGE = {
    "STARGAZER_STORE_ROOT": devbox_dashboard.STORE_ROOT,
    "STARGAZER_INDEX_URL": "http://dashboard-flytesnacks-development.flyte.svc.cluster.local",
    "STARGAZER_OWNER": devbox_dashboard.SUBJECT,
}


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
    """Deploy the dashboard for the stand-in user, as `cli/devbox_dashboard.py` does.

    Returns its URL. Deployed once per session, so it runs the current source
    and holds the index every other devbox test stores through.
    """
    return devbox_dashboard.deploy()


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
