"""
### Dashboard launcher — restore the asset index, then serve under Litestream.

The dashboard owns the user's asset index: a SQLite file on its own disk
(`STARGAZER_INDEX_URL`). Its disk doesn't survive scale-to-zero, so the file
is made durable in the bucket by Litestream, at
`<STARGAZER_STORE_ROOT>/users/<owner>/index`. This module is the dashboard's
startup command (`exec python -m app.dashboard_launch`):

1. Take the index lease (`Lease`), waiting for any other dashboard pod still
   replicating to stop. Litestream takes no lock of its own, and a redeploy
   starts the new pod while the old one runs: Knative keeps the old revision's
   pod for up to its autoscaling window, an hour here. Two Litestreams on one
   replica overwrite each other's files, and a write the old pod accepts after
   the new one has restored is lost (measured on the tenant).
2. Restore the index from the bucket if the file is missing and a replica
   exists. A failed restore stops the dashboard rather than starting it on
   an empty index.
3. Run `litestream replicate -exec "uvicorn …"` as a child (`supervise`) and
   pass it the SIGTERM Flyte's `fserve` sends at scale-to-zero: Litestream
   forwards it to uvicorn, waits for it to exit, then syncs one last time.
   Meanwhile the launcher checks it still holds the lease, and stops
   Litestream the same way if another pod has taken it over. Either way it
   releases the lease once Litestream has exited.

Both commands take the index file and the replica URL as arguments, so there
is no Litestream config file.

An S3-compatible store other than AWS reaches pods as `FLYTE_AWS_ENDPOINT`
and `FLYTE_AWS_*` keys: the endpoint rides on the replica URL (`?endpoint=`)
and the keys are copied to the `AWS_*` names Litestream reads. Without them
the pod's role supplies credentials.

Without a bucket root or an owner (local development, a deploy with no
store) there is nowhere durable to replicate to, and the launcher execs
uvicorn directly.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import flyte.storage

from app.init import init

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

# How often a replicating pod checks it still holds the lease, and how long a
# new pod waits for the old one to let go. Letting go takes uvicorn's graceful
# shutdown (up to 15 s, above) and Litestream's last sync.
LEASE_POLL_SECONDS = 2.0
HANDOVER_TIMEOUT_SECONDS = 60.0


def _owner_prefix(env: dict) -> str | None:
    """`<root>/users/<owner>` in a bucket store, or None without one."""
    root = env.get("STARGAZER_STORE_ROOT", "")
    owner = env.get("SG_OWNER_SUBJECT", "")
    if not root.startswith("s3://") or not owner:
        return None
    return f"{root.rstrip('/')}/users/{owner}"


def replica_url(env: dict) -> str | None:
    """The bucket location the index replicates to, or None without one.

    Needs a bucket store root (`s3://…`) and the dashboard's owner. The
    bucket's region rides on the URL (`?region=`), taken from `AWS_REGION`,
    `AWS_DEFAULT_REGION` or `STARGAZER_STORE_REGION`. It has to be given:
    without it Litestream looks the region up, which needs
    `s3:GetBucketLocation`, and the tenant's pod role doesn't grant it
    (measured: the restore failed with AccessDenied). An S3-compatible store's
    address rides on it too (`?endpoint=`, from `FLYTE_AWS_ENDPOINT`).
    """
    base = _owner_prefix(env)
    if base is None:
        return None
    url = f"{base}/index"
    query = {}
    if region := next((env[k] for k in _REGION_KEYS if env.get(k)), None):
        query["region"] = region
    if endpoint := env.get("FLYTE_AWS_ENDPOINT"):
        query["endpoint"] = endpoint
    return f"{url}?{urlencode(query)}" if query else url


def litestream_env(env: dict) -> dict:
    """`env` plus the store's keys under the `AWS_*` names Litestream reads.

    Flyte gives pods an S3-compatible store's keys as `FLYTE_AWS_*`. Keys
    already under the `AWS_*` names win.
    """
    out = dict(env)
    for name in ("ACCESS_KEY_ID", "SECRET_ACCESS_KEY"):
        if env.get(f"FLYTE_AWS_{name}") and not env.get(f"AWS_{name}"):
            out[f"AWS_{name}"] = env[f"FLYTE_AWS_{name}"]
    return out


def lease_prefix(env: dict) -> str | None:
    """Where the index lease lives, or None without a bucket store.

    Beside the replica rather than in it, so Litestream never lists it.
    """
    base = _owner_prefix(env)
    return f"{base}/index-lease" if base else None


def _fs(uri: str):
    """The fsspec filesystem `flyte.storage` resolves for `uri`."""
    return flyte.storage.get_underlying_filesystem(path=uri)


def _read(uri: str) -> str | None:
    """The pod named in a lease object, or None if it doesn't exist."""
    try:
        return _fs(uri).cat_file(uri).decode()
    except FileNotFoundError:
        return None


def _write(uri: str, pod: str) -> None:
    """Name `pod` in a lease object."""
    fs = _fs(uri)
    # A local root has directories and won't create the parent; a no-op on S3.
    fs.makedirs(uri.rsplit("/", 1)[0], exist_ok=True)
    fs.pipe_file(uri, pod.encode())


class Lease:
    """Lets one dashboard pod at a time replicate the owner's index.

    Two objects under the lease prefix, each naming a pod: `holder`, the pod
    replicating, and `released`, the last pod to stop. A starting pod names
    itself holder, then waits until the pod it displaced shows up as released,
    so its restore sees that pod's last sync. The displaced pod finds it no
    longer holds the lease within a poll and stops (`supervise`). A pod
    killed outright never releases, so the wait gives up after `timeout`.

    Plain overwrites are enough: only a starting pod writes `holder`, and a
    waiting pod looks in `released` only for the one pod it displaced.
    """

    def __init__(
        self,
        prefix: str,
        pod: str,
        poll: float = LEASE_POLL_SECONDS,
        timeout: float = HANDOVER_TIMEOUT_SECONDS,
    ):
        """A lease at `prefix` for `pod`, checked every `poll` seconds."""
        self.pod = pod
        self.poll = poll
        self.timeout = timeout
        self._holder = f"{prefix}/holder"
        self._released = f"{prefix}/released"

    def claim(self) -> None:
        """Take the lease, then wait for the pod that held it to let go.

        A pod finding its own name there is a restarted container, with no
        old process left to wait for.
        """
        previous = _read(self._holder)
        _write(self._holder, self.pod)
        if previous in (None, self.pod):
            return
        deadline = time.monotonic() + self.timeout
        while _read(self._released) != previous:
            if time.monotonic() >= deadline:
                print(
                    f"[sg] {previous} didn't let go of the index within "
                    f"{self.timeout:.0f}s; going on without it",
                    flush=True,
                )
                return
            time.sleep(self.poll)
        print(f"[sg] took the index over from {previous}", flush=True)

    def held(self) -> bool:
        """Whether this pod is still the holder.

        A failed check counts as held, so a blip in the store doesn't stop
        replication.
        """
        try:
            return _read(self._holder) == self.pod
        except Exception as exc:
            print(f"[sg] couldn't check the index lease: {exc}", flush=True)
            return True

    def release(self) -> None:
        """Record that this pod has stopped replicating."""
        _write(self._released, self.pod)


def supervise(cmd: list[str], env: dict, lease: Lease) -> int | None:
    """Run `cmd` (Litestream, wrapping uvicorn) while this pod holds the lease.

    Returns its exit code once it exits, or None once it has been stopped
    because another pod took the lease over. SIGTERM and SIGINT are passed on
    to it. The lease is released last, after Litestream's final sync.
    """
    child = subprocess.Popen(cmd, env=env)

    def forward(signum, _frame):
        child.send_signal(signum)

    previous = {
        sig: signal.signal(sig, forward) for sig in (signal.SIGTERM, signal.SIGINT)
    }
    try:
        while True:
            try:
                return child.wait(timeout=lease.poll)
            except subprocess.TimeoutExpired:
                pass
            if not lease.held():
                print(
                    "[sg] another dashboard pod took over the index; "
                    "stopping Litestream",
                    flush=True,
                )
                child.terminate()
                child.wait()
                return None
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        lease.release()


def _idle() -> None:
    """Do nothing until the pod is stopped.

    Exiting would only get the container restarted, and the restarted
    container would claim the lease back from the pod that took it over.
    """
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    while True:
        signal.pause()


def main() -> None:
    """Take the lease, restore the index, then serve under Litestream."""
    replica = replica_url(os.environ)
    if replica is None:
        os.execvp(SERVER[0], SERVER)
    env = litestream_env(os.environ)
    db = Path(os.environ["STARGAZER_INDEX_URL"].removeprefix("sqlite://")).expanduser()
    db.parent.mkdir(parents=True, exist_ok=True)
    print(f"[sg] index {db} -> {replica}", flush=True)
    # Storage credentials for the lease resolve through the Flyte client.
    init()
    lease = Lease(lease_prefix(os.environ), socket.gethostname())
    lease.claim()
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
        env=env,
    )
    code = supervise(
        ["litestream", "replicate", "-exec", " ".join(SERVER), str(db), replica],
        env,
        lease,
    )
    if code is None:
        _idle()
    sys.exit(code)


if __name__ == "__main__":
    main()
