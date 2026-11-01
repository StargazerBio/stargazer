"""Tests for specialize(): a raw storage record to its asset class."""

from pathlib import Path

import pytest
from conftest import SDK_TYPES

from stargazer.assets import specialize
from stargazer.assets.alignment import Alignment
from stargazer.assets.asset import Asset
from stargazer.assets.reference import Reference


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


def test_path_and_fields_come_from_the_record():
    result = specialize(
        record("Qmfasta", Path("/tmp/ref.fa"), asset="reference", build="GRCh38")
    )
    assert type(result) is Reference
    assert (result.path.path, result.path.name) == ("/tmp/ref.fa", "ref.fa")
    assert result.build == "GRCh38"


def test_non_str_fields_are_decoded():
    aln = specialize(
        record(asset="alignment", duplicates_marked="true", bqsr_applied="false")
    )
    vcf = specialize(
        record(asset="variants", sample_count="3", source_samples='["S1", "S2"]')
    )
    assert (aln.duplicates_marked, aln.bqsr_applied) == (True, False)
    assert (vcf.sample_count, vcf.source_samples) == (3, ["S1", "S2"])


def test_undeclared_keyvalues_kept_as_extras():
    """A key the class doesn't declare stays on the typed asset."""
    result = specialize(
        record(asset="alignment", sample_id="NA12878", custom_field="custom_value")
    )
    assert type(result) is Alignment
    assert result.sample_id == "NA12878"
    assert result.keyvalues == {"custom_field": "custom_value"}


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
    result = specialize(
        record("Qmbad", asset="variants", sample_id="S1", sample_count="three")
    )
    assert type(result) is Asset
    assert result.cid == "Qmbad"
    assert result.keyvalues == {
        "asset": "variants",
        "sample_id": "S1",
        "sample_count": "three",
    }
