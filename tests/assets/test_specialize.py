"""Tests for specialize(): a raw storage record to its asset class."""

import pytest
from conftest import SDK_TYPES

from stargazer.assets import specialize
from stargazer.assets.asset import Asset


def record(cid="Qm", path=None, **kv) -> dict:
    """Build a raw storage record for specialize(): an index row's shape."""
    return {
        "cid": cid,
        "uri": str(path) if path else None,
        "name": path.name if path else None,
        "keyvalues": kv,
    }


@pytest.mark.parametrize("cls", SDK_TYPES, ids=lambda cls: cls._asset_key)
def test_every_sdk_type_specializes_to_its_class(cls):
    """A record's `asset` key picks its class, and its CID comes along."""
    result = specialize(record("bafyX", asset=cls._asset_key))

    assert type(result) is cls
    assert result.cid == "bafyX"


def test_unregistered_key_is_a_bare_asset_with_its_keyvalues():
    """The registry is import-driven, per process, so the key must never collide
    with a registered class; even the tutorials register some on import."""
    result = specialize(record(asset="never_registered_key", sequencer="novaseq"))
    assert type(result) is Asset
    assert result.keyvalues == {"asset": "never_registered_key", "sequencer": "novaseq"}


def test_missing_asset_key_is_a_bare_asset():
    assert type(specialize(record("Qmbare"))) is Asset


def test_malformed_value_falls_back_to_a_bare_asset():
    """Strict at upload, graceful at query: a registered-key record whose non-str
    field doesn't JSON-parse degrades to a bare Asset with its keyvalues intact."""
    result = specialize(record("Qmbad", asset="anndata", sample_id="S1", n_obs="three"))
    assert type(result) is Asset
    assert result.cid == "Qmbad"
    assert result.keyvalues == {
        "asset": "anndata",
        "sample_id": "S1",
        "n_obs": "three",
    }
