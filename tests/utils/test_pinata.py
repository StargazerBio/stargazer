"""Tests for the Pinata client that don't call the API.

The ones that do are in tests/pinata/.
"""

import base64

import pytest

import stargazer.assets as assets_mod
from stargazer.assets.asset import Asset
from stargazer.utils.pinata import (
    PinataClient,
    _check_keyvalue_count,
    _check_keyvalue_lengths,
    _tus_metadata,
)

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
    encoded = _tus_metadata(filename="x.bam", keyvalues={"asset": "alignment"})
    pairs = dict(p.split(" ", 1) for p in encoded.split(","))
    assert base64.b64decode(pairs["filename"]).decode() == "x.bam"
    assert base64.b64decode(pairs["network"]).decode() == "public"
    assert base64.b64decode(pairs["keyvalues"]).decode() == '{"asset": "alignment"}'


def test_keyvalue_count_allows_nine():
    _check_keyvalue_count({f"k{i}": "v" for i in range(9)})


def test_keyvalue_count_rejects_ten_naming_both_numbers():
    with pytest.raises(ValueError, match=r"at most 9 .* has 10"):
        _check_keyvalue_count({f"k{i}": "v" for i in range(10)})


def test_keyvalue_lengths_allow_250_characters():
    _check_keyvalue_lengths({"k" * 250: "v" * 250})


def test_keyvalue_lengths_reject_a_251_character_value_naming_its_key():
    with pytest.raises(
        ValueError, match=r"at most 250 characters; 'source_samples' has 251"
    ):
        _check_keyvalue_lengths({"asset": "variants", "source_samples": "x" * 251})


def test_keyvalue_lengths_reject_a_251_character_key():
    with pytest.raises(ValueError, match=r"at most 250 characters; .* has 251"):
        _check_keyvalue_lengths({"k" * 251: "v"})


@pytest.mark.asyncio
async def test_upload_refuses_a_long_value_before_sending(tmp_path):
    """The check runs before any request, so a bad token is never used."""
    path = tmp_path / "x.txt"
    path.write_text("x")
    asset = Asset(keyvalues={"asset": "x", "note": "n" * 251})

    with pytest.raises(ValueError, match="at most 250 characters"):
        await PinataClient(jwt="unused").upload(asset, path)


@pytest.mark.asyncio
async def test_update_metadata_refuses_a_long_value_before_sending():
    with pytest.raises(ValueError, match="at most 250 characters"):
        await PinataClient(jwt="unused").update_metadata("bafy", {"note": "n" * 251})


@pytest.mark.parametrize("cls", SDK_TYPES, ids=lambda cls: cls._asset_key)
def test_every_type_fits_a_public_upload(cls):
    """Every declared field, the asset type and _owner fit on a new Pinata file."""
    kv = cls().to_keyvalues()
    kv["_owner"] = "someone"
    _check_keyvalue_count(kv)
