"""Tests for the dashboard launcher: when Litestream runs, what it replicates,
and the lease that lets only one dashboard pod replicate at a time.

The lease tests run the real `flyte.storage` calls against a local directory,
the same code path that talks to the bucket on the tenant.
"""

import os
import sys
import threading
import time

import pytest

from app.dashboard_launch import (
    SERVER,
    Lease,
    lease_prefix,
    litestream_env,
    replica_url,
    supervise,
)

# A child that would run far longer than any test: only supervise() stops it.
SLEEPER = [sys.executable, "-c", "import time; time.sleep(30)"]


def test_replica_lives_under_the_owner_in_the_store():
    """The index replicates to <store root>/users/<owner>/index."""
    env = {"STARGAZER_STORE_ROOT": "s3://bucket/stargazer/", "SG_OWNER_SUBJECT": "u1"}
    assert replica_url(env) == "s3://bucket/stargazer/users/u1/index"


def test_no_durable_store_means_no_litestream():
    """Without a bucket root or an owner, the dashboard just serves."""
    assert replica_url({"SG_OWNER_SUBJECT": "u1"}) is None
    assert (
        replica_url({"STARGAZER_STORE_ROOT": "/tmp/store", "SG_OWNER_SUBJECT": "u1"})
        is None
    )
    assert replica_url({"STARGAZER_STORE_ROOT": "s3://bucket/stargazer"}) is None


def test_replica_url_carries_the_region():
    """The bucket's region rides on the replica URL: AWS_REGION, then
    AWS_DEFAULT_REGION, then the deploy's own setting.

    It has to be given: Litestream's lookup needs s3:GetBucketLocation, which
    the tenant's role doesn't grant (measured on the tenant).
    """
    env = {"STARGAZER_STORE_ROOT": "s3://bucket/stargazer", "SG_OWNER_SUBJECT": "u1"}
    base = "s3://bucket/stargazer/users/u1/index"
    assert (
        replica_url({**env, "AWS_REGION": "us-west-2", "AWS_DEFAULT_REGION": "x"})
        == f"{base}?region=us-west-2"
    )
    assert (
        replica_url({**env, "AWS_DEFAULT_REGION": "eu-west-1"})
        == f"{base}?region=eu-west-1"
    )
    assert (
        replica_url({**env, "STARGAZER_STORE_REGION": "us-east-2"})
        == f"{base}?region=us-east-2"
    )


def test_replica_url_names_an_s3_compatible_endpoint():
    """A store that isn't AWS S3 (the devbox's) rides on the URL as endpoint=,
    taken from the FLYTE_AWS_ENDPOINT Flyte gives its pods there.

    Without it Litestream tries AWS and fails looking up the bucket's region
    (measured on the devbox).
    """
    env = {
        "STARGAZER_STORE_ROOT": "s3://flyte-data/stargazer",
        "SG_OWNER_SUBJECT": "u1",
        "FLYTE_AWS_ENDPOINT": "http://rustfs-svc.flyte:9000",
    }
    base = "s3://flyte-data/stargazer/users/u1/index"
    endpoint = "endpoint=http%3A%2F%2Frustfs-svc.flyte%3A9000"
    assert replica_url(env) == f"{base}?{endpoint}"
    assert (
        replica_url({**env, "AWS_REGION": "us-east-1"})
        == f"{base}?region=us-east-1&{endpoint}"
    )


def test_litestream_gets_the_stores_credentials():
    """Flyte hands the devbox store's keys to pods as FLYTE_AWS_*; Litestream
    reads AWS_*, so the launcher copies them across. Keys already set win."""
    env = {
        "PATH": "/usr/bin",
        "FLYTE_AWS_ACCESS_KEY_ID": "rustfs",
        "FLYTE_AWS_SECRET_ACCESS_KEY": "rustfsstorage",
    }
    assert litestream_env(env) == {
        **env,
        "AWS_ACCESS_KEY_ID": "rustfs",
        "AWS_SECRET_ACCESS_KEY": "rustfsstorage",
    }
    mine = {**env, "AWS_ACCESS_KEY_ID": "a", "AWS_SECRET_ACCESS_KEY": "b"}
    assert litestream_env(mine) == mine


def test_without_flyte_keys_litestream_env_is_unchanged():
    """On Union the pod role supplies credentials; nothing is added."""
    env = {"PATH": "/usr/bin", "AWS_REGION": "us-west-2"}
    assert litestream_env(env) == env


def test_server_is_the_dashboard():
    """The process Litestream wraps is the dashboard's uvicorn."""
    assert SERVER[:2] == ["uvicorn", "app.admin_app:asgi_app"]


def test_the_lease_lives_beside_the_replica():
    """The lease is under the owner too, outside Litestream's own prefix."""
    env = {"STARGAZER_STORE_ROOT": "s3://bucket/stargazer/", "SG_OWNER_SUBJECT": "u1"}
    assert lease_prefix(env) == "s3://bucket/stargazer/users/u1/index-lease"


@pytest.fixture
def prefix(tmp_path):
    """A fresh lease location in a local store."""
    return str(tmp_path / "users" / "u1" / "index-lease")


def _lease(prefix, pod, timeout=10.0):
    """A lease for `pod` that checks every 50 ms."""
    return Lease(prefix, pod, poll=0.05, timeout=timeout)


def _timed(fn):
    """Seconds `fn()` took."""
    started = time.monotonic()
    fn()
    return time.monotonic() - started


def test_the_first_pod_takes_the_lease_at_once(prefix):
    """With no one before it, a pod holds the lease without waiting."""
    lease = _lease(prefix, "pod-a")
    assert _timed(lease.claim) < 1
    assert lease.held()


def test_a_new_pod_waits_for_the_old_one_to_let_go(prefix):
    """A pod that finds another one holding the lease takes it over, then waits
    until the old one has released it before going on."""
    old = _lease(prefix, "pod-a")
    old.claim()
    new = _lease(prefix, "pod-b")
    threading.Timer(0.5, old.release).start()
    assert _timed(new.claim) >= 0.5
    assert new.held()
    assert not old.held()


def test_a_lease_let_go_cleanly_is_taken_at_once(prefix):
    """A dashboard that scaled to zero released the lease on its way out, so
    the next one starts without waiting."""
    old = _lease(prefix, "pod-a")
    old.claim()
    old.release()
    new = _lease(prefix, "pod-b")
    assert _timed(new.claim) < 1
    assert new.held()


def test_a_pod_that_never_lets_go_is_given_up_on(prefix):
    """A pod killed outright never releases; the new one takes over after the
    timeout instead of waiting forever."""
    _lease(prefix, "pod-a").claim()
    new = _lease(prefix, "pod-b", timeout=0.3)
    assert 0.3 <= _timed(new.claim) < 2
    assert new.held()


def test_a_restarted_container_takes_its_own_pods_lease_at_once(prefix):
    """The pod's name is the holder; a container restarted in the same pod
    has no old process to wait for."""
    _lease(prefix, "pod-a").claim()
    again = _lease(prefix, "pod-a")
    assert _timed(again.claim) < 1
    assert again.held()


def test_supervise_returns_the_childs_exit_code_and_lets_go(prefix):
    """When Litestream exits (at scale-to-zero), the pod releases the lease."""
    lease = _lease(prefix, "pod-a")
    lease.claim()
    code = supervise(
        [sys.executable, "-c", "raise SystemExit(3)"], os.environ.copy(), lease
    )
    assert code == 3
    new = _lease(prefix, "pod-b")
    assert _timed(new.claim) < 1
    assert new.held()


def test_supervise_stands_down_when_another_pod_takes_over(prefix):
    """A newer pod's claim stops this pod's Litestream and releases the lease,
    which lets the newer pod go on."""
    lease = _lease(prefix, "pod-a")
    lease.claim()
    new = _lease(prefix, "pod-b")
    taking_over = threading.Thread(target=new.claim)
    timer = threading.Timer(0.3, taking_over.start)
    timer.start()
    assert _timed(lambda: supervise(SLEEPER, os.environ.copy(), lease)) < 5
    timer.join()
    taking_over.join(timeout=5)
    assert not taking_over.is_alive()
    assert new.held()


def test_standing_down_is_not_an_exit(prefix):
    """supervise() tells a stand-down apart from Litestream exiting."""
    lease = _lease(prefix, "pod-a")
    lease.claim()
    threading.Timer(0.3, _lease(prefix, "pod-b", timeout=0).claim).start()
    assert supervise(SLEEPER, os.environ.copy(), lease) is None
