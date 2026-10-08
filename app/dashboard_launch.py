"""
### Dashboard launcher — restore the asset index, then serve under Litestream.

The dashboard owns the user's asset index: a SQLite file on its own disk
(`STARGAZER_INDEX_URL`). Its disk doesn't survive scale-to-zero, so the file
is made durable in the bucket by Litestream, at
`<STARGAZER_STORE_ROOT>/users/<owner>/index`. This module is the dashboard's
startup command (`exec python -m app.dashboard_launch`):

1. Restore the index from the bucket if the file is missing and a replica
   exists. A failed restore stops the dashboard rather than starting it on
   an empty index.
2. `exec` into `litestream replicate -exec "uvicorn …"`, so Litestream is the
   process Flyte's `fserve` signals at scale-to-zero: it forwards SIGTERM to
   uvicorn, waits for it to exit, then syncs one last time.

Both commands take the index file and the replica URL as arguments, so there
is no Litestream config file.

Without a bucket root or an owner (local development, a deploy with no
store) there is nowhere durable to replicate to, and the launcher execs
uvicorn directly.

The exec chain matters as much as in the notebook pods (see
`app/launch-notebook.sh`): the AppEnvironment args start with `exec`, Python
replaces itself with Litestream, and Litestream runs uvicorn as its child.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os
import subprocess
from pathlib import Path

SERVER = [
    "uvicorn",
    "app.admin_app:asgi_app",
    "--host",
    "0.0.0.0",
    "--port",
    "8080",
    "--timeout-graceful-shutdown",
    "15",
]


_REGION_KEYS = ("AWS_REGION", "AWS_DEFAULT_REGION", "STARGAZER_STORE_REGION")


def replica_url(env: dict) -> str | None:
    """The bucket location the index replicates to, or None without one.

    Needs a bucket store root (`s3://…`) and the dashboard's owner. The
    bucket's region rides on the URL (`?region=`), taken from `AWS_REGION`,
    `AWS_DEFAULT_REGION` or `STARGAZER_STORE_REGION`. It has to be given:
    without it Litestream looks the region up, which needs
    `s3:GetBucketLocation`, and the tenant's pod role doesn't grant it
    (measured: the restore failed with AccessDenied).
    """
    root = env.get("STARGAZER_STORE_ROOT", "")
    owner = env.get("SG_OWNER_SUBJECT", "")
    if not root.startswith("s3://") or not owner:
        return None
    url = f"{root.rstrip('/')}/users/{owner}/index"
    region = next((env[k] for k in _REGION_KEYS if env.get(k)), None)
    return f"{url}?region={region}" if region else url


def main() -> None:
    """Restore the index, then hand the process to Litestream (or uvicorn)."""
    replica = replica_url(os.environ)
    if replica is None:
        os.execvp(SERVER[0], SERVER)
    db = Path(os.environ["STARGAZER_INDEX_URL"].removeprefix("sqlite://")).expanduser()
    db.parent.mkdir(parents=True, exist_ok=True)
    print(f"[sg] index {db} -> {replica}", flush=True)
    subprocess.run(
        [
            "litestream",
            "restore",
            "-if-db-not-exists",
            "-if-replica-exists",
            "-o",
            str(db),
            replica,
        ],
        check=True,
    )
    os.execvp(
        "litestream",
        ["litestream", "replicate", "-exec", " ".join(SERVER), str(db), replica],
    )


if __name__ == "__main__":
    main()
