"""Tests for the Pinata client that don't call the API.

The ones that do are in tests/pinata/.
"""

import base64

from stargazer.utils.pinata import _tus_metadata


def test_tus_metadata_encoding():
    """TUS Upload-Metadata is comma-joined `key b64(value)` pairs."""
    encoded = _tus_metadata(
        filename="x.bam", network="private", keyvalues={"asset": "alignment"}
    )
    pairs = dict(p.split(" ", 1) for p in encoded.split(","))
    assert base64.b64decode(pairs["filename"]).decode() == "x.bam"
    assert base64.b64decode(pairs["network"]).decode() == "private"
    assert base64.b64decode(pairs["keyvalues"]).decode() == '{"asset": "alignment"}'
