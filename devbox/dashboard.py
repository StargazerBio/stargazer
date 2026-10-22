#!/usr/bin/env python3
"""
Deploy a Stargazer dashboard on the local devbox.

The app tier is built for Union, where onboarding gives each user a project
and Union's login sits in front of every app. The devbox has neither, so this
calls the same `app.deploy.deploy_dashboard` with devbox settings, and
everything devbox-specific about the dashboard lives here; `app/` stays
target-agnostic:

- The default project and a stand-in owner, `devbox-user`, who is also the
  asset owner and the folder in the store.
- `SG_STAND_IN_SUBJECT`. The dashboard reads the user from `X-User-Subject`,
  which only Union's login sets, so without it every page answers `401 not
  signed in`. `app.identity` treats a request with no subject as the stand-in;
  `app.config.stand_in_subject` ignores it when `STARGAZER_TARGET=union`, and
  this script refuses to run off the devbox. A real subject header still wins.
- The store under `s3://flyte-data/stargazer`, the devbox's bucket (rustfs).
- The index on the devbox's Postgres server (`devbox/postgres.yaml`), standing
  in for the user's DSQL table on Union: the dashboard's asset browser reads
  that database, and the notebook pods it launches get the same URL.
- A `kubectl` port-forward to the object store while the code bundle uploads,
  since uploads go to the in-cluster signed-URL host (`devbox/setup.sh`).

Runs submitted from this machine store into the devbox's bucket and index
without the dashboard, when these are exported (`stargazer.config` forwards
them into every pod) and the storage port-forward is open:

    export STARGAZER_STORE_ROOT=s3://flyte-data/stargazer
    export STARGAZER_INDEX_URL=postgresql://stargazer:stargazer@postgres.stargazer.svc.cluster.local:5432/stargazer
    export STARGAZER_OWNER=devbox-user
    kubectl port-forward -n flyte svc/rustfs-svc 9000:9000

Usage (after `devbox/setup.sh`), printing the dashboard's URL,
`http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081`:
    uv run --all-extras python devbox/dashboard.py
"""

import socket
import subprocess
import time
from contextlib import contextmanager

from app import config
from app.deploy import deploy_dashboard
from app.init import init
from stargazer.config import PROJECT_ROOT

# The stand-in user, the bucket every devbox deploy stores under, and the
# asset index: the Postgres server in `devbox/postgres.yaml`, whose user,
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
        raise SystemExit("devbox/dashboard.py needs STARGAZER_TARGET=devbox.")
    init(config.FLYTE_CONFIG, root_dir=PROJECT_ROOT)
    print(f"Dashboard: {deploy()}")


if __name__ == "__main__":
    main()
