"""Pinata assigns the CIDs we compute locally.

Uploads fresh bytes to Pinata and compares the CID Pinata assigns with ours,
so a change to Pinata's chunking or layout fails it. The CIDs themselves are
pinned in tests/utils/test_cid.py.
"""

import os

import pytest

from stargazer.assets.asset import Asset
from stargazer.utils.cid import compute_cid
from stargazer.utils.pinata import TUS_THRESHOLD_BYTES, PinataClient

# 175 chunks of 256 KiB: one more than a single node can link.
ONE_PAST_A_NODE = 174 * 256 * 1024 + 1


@pytest.mark.parametrize(
    "size",
    [
        pytest.param(1024, id="one-block"),
        pytest.param(2 * 256 * 1024 + 1, id="three-chunks"),
        pytest.param(ONE_PAST_A_NODE, id="two-levels"),
        pytest.param(TUS_THRESHOLD_BYTES + 1, id="resumable-upload"),
    ],
)
async def test_pinata_assigns_the_same_cid(size, tmp_path):
    """Pinata's CID for a new upload equals ours, for each tree shape and both
    upload paths (plain POST, and TUS past TUS_THRESHOLD_BYTES).

    Random bytes make Pinata chunk the file itself: it can't hand back a CID
    it stored earlier, under older settings.
    """
    path = tmp_path / f"cid_drift_{size}.bin"
    path.write_bytes(os.urandom(size))
    expected = compute_cid(path)

    client = PinataClient()
    uploaded = Asset(keyvalues={"asset": "cid_drift_probe"})
    await client.upload(uploaded, path)
    try:
        assert uploaded.cid == expected
    finally:
        await client.delete(Asset(cid=uploaded.cid))
