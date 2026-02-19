"""Tests for the marshal module."""

from pathlib import Path

from stargazer.marshal import marshal_input, marshal_output
from stargazer.types import Reference, Alignment, Reads, Variants
from stargazer.tasks.gatk.variant_recalibrator import VQSRResource


# ---------------------------------------------------------------------------
# Input marshaling
# ---------------------------------------------------------------------------


def test_marshal_input_reference_from_dict():
    """Reference dict is converted via from_dict."""
    d = {"build": "GRCh38"}
    result = marshal_input(d, Reference)
    assert isinstance(result, Reference)
    assert result.build == "GRCh38"


def test_marshal_input_alignment_from_dict():
    d = {"sample_id": "NA12878"}
    result = marshal_input(d, Alignment)
    assert isinstance(result, Alignment)
    assert result.sample_id == "NA12878"


def test_marshal_input_reads_from_dict():
    d = {"sample_id": "NA12878"}
    result = marshal_input(d, Reads)
    assert isinstance(result, Reads)
    assert result.sample_id == "NA12878"


def test_marshal_input_variants_from_dict():
    d = {"sample_id": "NA12878"}
    result = marshal_input(d, Variants)
    assert isinstance(result, Variants)
    assert result.sample_id == "NA12878"


def test_marshal_input_vqsr_resource():
    """VQSRResource is constructed via **kwargs."""
    d = {
        "name": "hapmap",
        "vcf_name": "hapmap.vcf.gz",
        "known": "false",
        "training": "true",
        "truth": "true",
        "prior": "15.0",
    }
    result = marshal_input(d, VQSRResource)
    assert isinstance(result, VQSRResource)
    assert result.name == "hapmap"
    assert result.prior == "15.0"


def test_marshal_input_path():
    result = marshal_input("/tmp/file.txt", Path)
    assert isinstance(result, Path)
    assert str(result) == "/tmp/file.txt"


def test_marshal_input_list_variants():
    """list[Variants] marshals each element."""
    ds = [{"sample_id": "S1"}, {"sample_id": "S2"}]
    result = marshal_input(ds, list[Variants])
    assert len(result) == 2
    assert all(isinstance(v, Variants) for v in result)
    assert result[0].sample_id == "S1"


def test_marshal_input_list_str():
    """list[str] passes through."""
    result = marshal_input(["a", "b"], list[str])
    assert result == ["a", "b"]


def test_marshal_input_optional_none():
    """None stays None for optional types."""
    result = marshal_input(None, Reference | None)
    assert result is None


def test_marshal_input_optional_with_value():
    """Optional with actual value unwraps and marshals."""
    d = {"build": "T2T"}
    result = marshal_input(d, Reference | None)
    assert isinstance(result, Reference)
    assert result.build == "T2T"


def test_marshal_input_primitives():
    """Primitives pass through."""
    assert marshal_input("hello", str) == "hello"
    assert marshal_input(42, int) == 42
    assert marshal_input(True, bool) is True
    assert marshal_input(3.14, float) == 3.14


def test_marshal_input_dict_passthrough():
    """dict[str, str] passes through."""
    d = {"key": "value"}
    result = marshal_input(d, dict[str, str])
    assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# Output marshaling
# ---------------------------------------------------------------------------


def test_marshal_output_reference():
    """Reference with to_dict is serialized."""
    ref = Reference(build="GRCh38")
    result = marshal_output(ref)
    assert isinstance(result, dict)
    assert result["build"] == "GRCh38"


def test_marshal_output_path():
    result = marshal_output(Path("/tmp/file.txt"))
    assert result == "/tmp/file.txt"


def test_marshal_output_tuple():
    """Tuple becomes {"o0": ..., "o1": ...}."""
    result = marshal_output((Path("/a"), Path("/b")))
    assert result == {"o0": "/a", "o1": "/b"}


def test_marshal_output_list():
    refs = [Reference(build="A"), Reference(build="B")]
    result = marshal_output(refs)
    assert len(result) == 2
    assert result[0]["build"] == "A"


def test_marshal_output_none():
    assert marshal_output(None) is None


def test_marshal_output_primitive():
    assert marshal_output("hello") == "hello"
    assert marshal_output(42) == 42
