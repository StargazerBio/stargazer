"""Tests for the Pinata client that don't call the API.

The ones that do are in tests/pinata/.
"""

import base64

import pytest

import stargazer.assets as assets_mod
from stargazer.assets.asset import Asset
from stargazer.utils.pinata import _check_keyvalue_count, _tus_metadata

SDK_TYPES = sorted(
    (
        obj
        for name in assets_mod.__all__
        if isinstance(obj := getattr(assets_mod, name), type)
        and issubclass(obj, Asset)
        and obj._asset_key
    ),
    key=lambda cls: cls._asset_key,
)


def test_tus_metadata_encoding():
    """TUS Upload-Metadata is comma-joined `key b64(value)` pairs."""
    encoded = _tus_metadata(
        filename="x.bam", network="private", keyvalues={"asset": "alignment"}
    )
    pairs = dict(p.split(" ", 1) for p in encoded.split(","))
    assert base64.b64decode(pairs["filename"]).decode() == "x.bam"
    assert base64.b64decode(pairs["network"]).decode() == "private"
    assert base64.b64decode(pairs["keyvalues"]).decode() == '{"asset": "alignment"}'


def test_keyvalue_count_allows_nine():
    _check_keyvalue_count({f"k{i}": "v" for i in range(9)})


def test_keyvalue_count_rejects_ten_naming_both_numbers():
    with pytest.raises(ValueError, match=r"at most 9 .* has 10"):
        _check_keyvalue_count({f"k{i}": "v" for i in range(10)})


@pytest.mark.parametrize("cls", SDK_TYPES, ids=lambda cls: cls._asset_key)
def test_every_type_fits_a_public_upload(cls):
    """Every declared field, the asset type and _owner fit on a new Pinata file."""
    kv = cls().to_keyvalues()
    kv["_owner"] = "someone"
    _check_keyvalue_count(kv)
