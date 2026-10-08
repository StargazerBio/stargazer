#!/usr/bin/env python3
"""
Deploy a Stargazer dashboard on the local devbox.

The devbox has no Union users or login, so instead of `stargazer-users
onboard` this deploys one dashboard into the default project for a stand-in
user, storing under the devbox's bucket. It holds a `kubectl` port-forward to
the devbox's object store open while the code bundle uploads. Why each piece
is needed: `.opencode/reference/devbox_workarounds.md`.

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

# The stand-in user and the bucket every devbox deploy stores under.
SUBJECT = "devbox-user"
STORE_ROOT = "s3://flyte-data/stargazer"


def _port_open(port: int) -> bool:
    """Whether something already listens on localhost:`port`."""
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def storage_port_forward():
    """Hold `localhost:9000 → svc/rustfs-svc:9000` open; reuse one already open."""
    if _port_open(9000):
        yield
        return
    proc = subprocess.Popen(
        ["kubectl", "port-forward", "-n", "flyte", "svc/rustfs-svc", "9000:9000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            if _port_open(9000):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("kubectl port-forward to the devbox store didn't open")
        yield
    finally:
        proc.terminate()


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
