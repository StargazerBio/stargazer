#!/usr/bin/env python3
"""
Deploy a Stargazer dashboard on the local devbox.

The devbox has no Union users or login, so instead of `stargazer-users
onboard` this deploys one dashboard into the default project for a stand-in
user, storing under the devbox's bucket and indexing in the devbox's Postgres
server (which `cli/devbox-setup.sh` starts). It holds a `kubectl`
port-forward to the devbox's object store open while the code bundle
uploads. Why each piece is needed: `.opencode/reference/devbox_workarounds.md`.

Usage (after `cli/devbox-setup.sh`):
    uv run --all-extras python cli/devbox_dashboard.py
"""

import socket
import subprocess
import time
from contextlib import contextmanager

from app import config
from app.init import init
from app.onboard import deploy_dashboard
from stargazer.config import PROJECT_ROOT

# The stand-in user, the bucket every devbox deploy stores under, and the
# asset index: the Postgres server `cli/devbox-setup.sh` starts, whose user,
# password and database this URL must match.
SUBJECT = "devbox-user"
STORE_ROOT = "s3://flyte-data/stargazer"
INDEX_URL = (
    "postgresql://stargazer:stargazer@"
    "postgres.stargazer.svc.cluster.local:5432/stargazer"
)


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


def storage_port_forward():
    """Hold `localhost:9000 → svc/rustfs-svc:9000` open; reuse one already open."""
    return port_forward("flyte", "svc/rustfs-svc", 9000, 9000)


def deploy() -> str:
    """Deploy the dashboard for the stand-in user; return its URL."""
    with storage_port_forward():
        return deploy_dashboard(
            config.FLYTE_PROJECT,
            SUBJECT,
            extra_env={
                "SG_STAND_IN_SUBJECT": SUBJECT,
                "STARGAZER_WORKSPACE_ROOT": STORE_ROOT,
                "STARGAZER_STORE_ROOT": STORE_ROOT,
                "STARGAZER_INDEX_URL": INDEX_URL,
            },
        )


def main() -> None:
    """Refuse off the devbox, then deploy and print the dashboard's URL."""
    if config.TARGET != "devbox":
        raise SystemExit("devbox_dashboard.py needs STARGAZER_TARGET=devbox.")
    init(config.FLYTE_CONFIG, root_dir=PROJECT_ROOT)
    print(f"Dashboard: {deploy()}")


if __name__ == "__main__":
    main()
