"""Tasks for `devbox_storage_probe.py`: store files in one pod, read them in another.

Imported inside the probe's pods, so it imports nothing from `app/` (the
dashboard's module mounts files the installed package doesn't carry). The
driver sets `SG_PROBE_IMAGE` to the devbox dashboard's image before importing
this module, and the env passes it on: `probe` submits its children from its
own pod, which would otherwise give them Flyte's default image.
"""

import os
from pathlib import Path

import flyte

from stargazer.assets.asset import Asset, assemble
from stargazer.utils.storage import default_client

# What a notebook pod launched from the devbox dashboard gets: the devbox
# bucket, the dashboard's in-cluster address, the stand-in owner. The driver
# checks these against `app.onboard`'s devbox settings.
STORE_ROOT = "s3://flyte-data/stargazer"
INDEX_URL = "http://dashboard-flytesnacks-development.flyte.svc.cluster.local"
OWNER = "devbox-user"

IMAGE = os.environ.get("SG_PROBE_IMAGE", "auto")

env = flyte.TaskEnvironment(
    name="sg_devbox_storage_probe",
    image=IMAGE,
    env_vars={
        "SG_PROBE_IMAGE": IMAGE,
        "STARGAZER_TARGET": "devbox",
        "STARGAZER_STORE_ROOT": STORE_ROOT,
        "STARGAZER_INDEX_URL": INDEX_URL,
        "STARGAZER_OWNER": OWNER,
    },
    resources=flyte.Resources(cpu=1, memory=("256Mi", "512Mi")),
)


@env.task
async def produce(n: int, tag: str) -> list[str]:
    """Write n small files and store each as an asset."""
    cids = []
    for i in range(n):
        path = Path(default_client.local_dir) / f"probe_{tag}_{i}.txt"
        path.write_text(f"{tag}:{i}")
        asset = Asset(keyvalues={"asset": "devbox_probe", "tag": tag, "i": str(i)})
        await asset.update(path)
        cids.append(asset.cid)
    return cids


@env.task
async def consume(tag: str) -> list[str]:
    """Find the tag's assets through the index and read each one back."""
    found = await assemble(asset="devbox_probe", tag=tag)
    return sorted([(await a.fetch()).read_text() for a in found])


@env.task
async def probe(n: int, tag: str) -> list[str]:
    """Produce in one pod, consume in another."""
    await produce(n, tag)
    return await consume(tag)
