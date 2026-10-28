"""Asset storage on the devbox.

Files stored from one pod are found and read back from another, indexed in
the devbox's Postgres server under the stand-in user's folder of the devbox
bucket, and still indexed after the Postgres pod restarts. A typed asset's extra keys travel with it between pods.
"""

import json
import subprocess
import time
import uuid

import psycopg
import pytest

from . import pod_tasks
from .conftest import STORAGE

N = 3


@pytest.fixture(scope="module")
def tag(devbox_run) -> str:
    """Store N small files from one pod under a fresh tag; return the tag."""
    tag = uuid.uuid4().hex[:8]
    devbox_run(pod_tasks.produce, n=N, tag=tag)
    return tag


def _rows(index_query, tag: str) -> list[dict]:
    """The index rows for the tag, in the order they were written."""
    rows = index_query({"asset": "devbox_probe", "tag": tag})
    return sorted(rows, key=lambda row: row["keyvalues"]["i"])


def test_read_back_from_another_pod(tag, devbox_run):
    """A second pod finds every file with `assemble()` and reads it back."""
    got = devbox_run(pod_tasks.consume, tag=tag).outputs()[0]
    assert got == [f"{tag}:{i}" for i in range(N)]


def test_indexed_in_postgres(tag, index_query):
    """One row per file, under the stand-in user's folder, owned by them."""
    rows = _rows(index_query, tag)
    assert [row["name"] for row in rows] == [f"probe_{tag}_{i}.txt" for i in range(N)]
    for row in rows:
        assert row["uri"] == (
            f"{STORAGE['STARGAZER_STORE_ROOT']}/users/{STORAGE['STARGAZER_OWNER']}"
            f"/assets/{row['cid']}/{row['name']}"
        )
        assert row["keyvalues"]["_owner"] == STORAGE["STARGAZER_OWNER"]


def test_extra_keyvalue_travels_between_pods(devbox_run):
    """An R1's extra key survives a task handoff and an `assemble()` from another pod."""
    lane = uuid.uuid4().hex[:8]
    handed, found = json.loads(
        devbox_run(pod_tasks.lane_round_trip, lane=lane).outputs()[0]
    )
    assert handed["cid"] == found["cid"]
    assert (handed["type"], handed["keyvalues"]) == ("R1", {"lane": lane})
    # The stored row carries the stamped owner, and a found asset keeps it.
    assert (found["type"], found["keyvalues"]) == (
        "R1",
        {"lane": lane, "_owner": STORAGE["STARGAZER_OWNER"]},
    )


def test_index_survives_a_postgres_restart(tag, index_query):
    """After its pod is deleted, Postgres comes back with the same rows."""
    before = _rows(index_query, tag)
    assert len(before) == N
    subprocess.run(
        [
            "kubectl", "--context", "flyte-devbox", "delete", "pod",
            "-n", "stargazer", "-l", "app=postgres", "--wait=true",
        ],
        capture_output=True, check=True,
    )  # fmt: skip
    deadline = time.monotonic() + 300
    while True:
        try:
            after = _rows(index_query, tag)
            break
        except RuntimeError, psycopg.OperationalError:
            # No pod to forward to yet, or the server isn't accepting yet.
            if time.monotonic() > deadline:
                pytest.fail("Postgres didn't come back within 5 minutes")
            time.sleep(5)
    assert after == before
