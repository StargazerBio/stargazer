"""Asset storage on the devbox.

Files stored from one pod are found and read back from another, indexed by
the dashboard under the stand-in user's folder of the devbox bucket, and
still indexed after the dashboard's pod restarts.
"""

import subprocess
import time
import uuid

import httpx
import pytest

from . import pod_tasks

N = 3


@pytest.fixture(scope="module")
def tag(dashboard, devbox_run) -> str:
    """Store N small files from one pod under a fresh tag; return the tag."""
    tag = uuid.uuid4().hex[:8]
    devbox_run(pod_tasks.produce, n=N, tag=tag)
    return tag


def _rows(dashboard: str, tag: str) -> list[dict]:
    """The dashboard's index rows for the tag, in the order they were written."""
    response = httpx.post(
        f"{dashboard}/index/query",
        json={"filters": {"asset": "devbox_probe", "tag": tag}},
        timeout=30,
    )
    response.raise_for_status()
    return sorted(response.json(), key=lambda row: row["keyvalues"]["i"])


def test_read_back_from_another_pod(tag, devbox_run):
    """A second pod finds every file with `assemble()` and reads it back."""
    got = devbox_run(pod_tasks.consume, tag=tag).outputs()[0]
    assert got == [f"{tag}:{i}" for i in range(N)]


def test_indexed_by_the_dashboard(tag, dashboard):
    """One row per file, under the stand-in user's folder, owned by them."""
    rows = _rows(dashboard, tag)
    assert [row["name"] for row in rows] == [f"probe_{tag}_{i}.txt" for i in range(N)]
    for row in rows:
        assert row["uri"] == (
            "s3://flyte-data/stargazer/users/devbox-user/assets/"
            f"{row['cid']}/{row['name']}"
        )
        assert row["keyvalues"]["_owner"] == "devbox-user"


def test_index_survives_a_dashboard_restart(tag, dashboard):
    """After its pod is deleted, the dashboard comes back with the same rows."""
    before = _rows(dashboard, tag)
    pods = subprocess.run(
        ["kubectl", "get", "pods", "-n", "flyte", "-o", "name"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    subprocess.run(
        ["kubectl", "delete", "-n", "flyte", *[p for p in pods if "dashboard" in p]],
        capture_output=True,
        check=True,
    )
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{dashboard}/health", timeout=10).status_code == 200:
                break
        except httpx.HTTPError:
            pass  # the new pod isn't serving yet
        time.sleep(5)
    else:
        pytest.fail("the dashboard didn't come back within 5 minutes")
    assert _rows(dashboard, tag) == before
