"""
Tests for annotation-based field declarations on Asset subclasses.
"""

import pytest

from stargazer.types import specialize
from stargazer.types.asset import Asset
from stargazer.types.alignment import Alignment
from stargazer.types.reads import R1
from stargazer.types.variants import Variants


# ---------------------------------------------------------------------------
# Auto-derivation from annotations
# ---------------------------------------------------------------------------


def test_r1_field_defaults_all_str():
    assert R1._field_defaults == {
        "sample_id": "",
        "mate_cid": "",
        "sequencing_platform": "",
    }


def test_r1_field_types_empty():
    # All str fields → _field_types should not include them
    assert R1._field_types == {}


def test_alignment_field_types():
    assert Alignment._field_types == {"duplicates_marked": bool, "bqsr_applied": bool}


def test_alignment_field_defaults_all_fields():
    fd = Alignment._field_defaults
    expected_keys = {
        "sample_id",
        "format",
        "sorted",
        "duplicates_marked",
        "bqsr_applied",
        "tool",
        "reference_cid",
        "r1_cid",
    }
    assert set(fd.keys()) == expected_keys


def test_variants_field_types():
    assert Variants._field_types == {"sample_count": int, "source_samples": list}


# ---------------------------------------------------------------------------
# Key enforcement
# ---------------------------------------------------------------------------


def test_unknown_key_raises_on_subclass():
    r1 = R1()
    with pytest.raises(ValueError, match="does not allow keyvalue"):
        r1.unknown = "x"


def test_base_asset_allows_any_key():
    a = Asset(keyvalues={"anything": "goes"})
    # no error — base Asset is unrestricted
    a.other_key = "also fine"


def test_allowed_key_works():
    a = Alignment()
    a.tool = "bwa"
    assert a.keyvalues["tool"] == "bwa"


# ---------------------------------------------------------------------------
# Coercion
# ---------------------------------------------------------------------------


def test_bool_true_coercion():
    a = Alignment(duplicates_marked=True)
    assert a.keyvalues["duplicates_marked"] == "true"


def test_bool_read_back():
    a = Alignment(duplicates_marked=True)
    assert a.duplicates_marked is True


def test_bool_false_coercion():
    a = Alignment(duplicates_marked=False)
    assert a.keyvalues["duplicates_marked"] == "false"


def test_int_coercion():
    v = Variants(sample_count=3)
    assert v.keyvalues["sample_count"] == "3"


def test_int_read_back():
    v = Variants(sample_count=3)
    assert v.sample_count == 3


def test_list_none_coercion():
    v = Variants(source_samples=None)
    assert v.keyvalues["source_samples"] == ""


def test_list_coercion():
    v = Variants(source_samples=["A", "B"])
    assert v.keyvalues["source_samples"] == "A,B"


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_r1_kwarg_written_to_keyvalues():
    assert R1(sample_id="NA12878").keyvalues["sample_id"] == "NA12878"


def test_r1_kwarg_readable_as_attr():
    assert R1(sample_id="NA12878").sample_id == "NA12878"


def test_r1_asset_keyvalue_auto_set():
    assert R1().keyvalues["asset"] == "r1"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_r1_round_trip():
    r1 = R1(sample_id="NA12878")
    assert R1.from_dict(r1.to_dict()).sample_id == "NA12878"


def test_specialize_preserves_fields():
    a = Asset(keyvalues={"asset": "r1", "sample_id": "NA12878"})
    s = specialize(a)
    assert s.sample_id == "NA12878"
