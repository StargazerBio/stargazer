"""Tests for Asset specialization."""

from pathlib import Path

from stargazer.types.asset import Asset
from stargazer.types import specialize
from stargazer.types.reference import (
    Reference,
    ReferenceIndex,
    SequenceDict,
    AlignerIndex,
)
from stargazer.types.alignment import Alignment, AlignmentIndex
from stargazer.types.variants import Variants, VariantsIndex
from stargazer.types.reads import R1, R2


class TestSpecialize:
    """specialize() converts a base Asset to the correct derived type."""

    def test_reference(self):
        base = Asset(
            cid="Qmfasta",
            path=Path("/tmp/ref.fa"),
            keyvalues={"asset": "reference", "build": "GRCh38"},
        )
        result = specialize(base)
        assert type(result) is Reference
        assert result.cid == "Qmfasta"
        assert result.path == Path("/tmp/ref.fa")
        assert result.build == "GRCh38"

    def test_reference_index(self):
        base = Asset(
            cid="Qmfaidx",
            keyvalues={"asset": "reference_index", "build": "T2T"},
        )
        result = specialize(base)
        assert type(result) is ReferenceIndex
        assert result.build == "T2T"

    def test_sequence_dict(self):
        base = Asset(
            cid="Qmdict",
            keyvalues={"asset": "sequence_dict"},
        )
        result = specialize(base)
        assert type(result) is SequenceDict

    def test_aligner_index(self):
        base = Asset(
            cid="Qmaln",
            keyvalues={"asset": "aligner_index", "aligner": "bwa"},
        )
        result = specialize(base)
        assert type(result) is AlignerIndex
        assert result.aligner == "bwa"

    def test_alignment(self):
        base = Asset(
            cid="Qmbam",
            keyvalues={
                "asset": "alignment",
                "sample_id": "NA12878",
                "duplicates_marked": "true",
                "bqsr_applied": "false",
            },
        )
        result = specialize(base)
        assert type(result) is Alignment
        assert result.sample_id == "NA12878"
        assert result.duplicates_marked is True
        assert result.bqsr_applied is False

    def test_alignment_index(self):
        base = Asset(
            cid="Qmbai",
            keyvalues={"asset": "alignment_index", "sample_id": "S1"},
        )
        result = specialize(base)
        assert type(result) is AlignmentIndex

    def test_variants(self):
        base = Asset(
            cid="Qmvcf",
            keyvalues={
                "asset": "variants",
                "sample_id": "S1",
                "sample_count": "3",
                "source_samples": "S1,S2,S3",
            },
        )
        result = specialize(base)
        assert type(result) is Variants
        assert result.sample_count == 3
        assert result.source_samples == ["S1", "S2", "S3"]

    def test_variants_index(self):
        base = Asset(
            cid="Qmtbi",
            keyvalues={"asset": "variants_index"},
        )
        result = specialize(base)
        assert type(result) is VariantsIndex

    def test_r1(self):
        base = Asset(
            cid="Qmr1",
            keyvalues={"asset": "r1", "sample_id": "S1"},
        )
        result = specialize(base)
        assert type(result) is R1

    def test_r2(self):
        base = Asset(
            cid="Qmr2",
            keyvalues={"asset": "r2", "sample_id": "S1"},
        )
        result = specialize(base)
        assert type(result) is R2

    def test_unknown_returns_base(self):
        """Unknown asset key returns the original Asset unchanged."""
        base = Asset(
            cid="Qmunk",
            keyvalues={"asset": "unknown_thing"},
        )
        result = specialize(base)
        assert result is base

    def test_missing_asset_keyvalue_returns_base(self):
        """Asset with no 'asset' keyvalue returns itself."""
        base = Asset(cid="Qmbare")
        result = specialize(base)
        assert result is base

    def test_already_specialized_is_idempotent(self):
        """Calling specialize on a derived instance returns a new instance of the same type."""
        original = Alignment(
            cid="Qmbam",
            keyvalues={"asset": "alignment", "sample_id": "S1"},
        )
        result = specialize(original)
        assert type(result) is Alignment
        assert result.cid == original.cid

    def test_unknown_keyvalues_dropped_on_specialize(self):
        """Undeclared keyvalues are dropped during specialization (field enforcement)."""
        base = Asset(
            cid="Qm123",
            keyvalues={
                "asset": "alignment",
                "sample_id": "NA12878",
                "custom_field": "custom_value",
            },
        )
        result = specialize(base)
        assert result.sample_id == "NA12878"
        assert "custom_field" not in result.keyvalues

    def test_does_not_mutate_original(self):
        """The original Asset is not modified."""
        base = Asset(
            cid="Qmorig",
            path=Path("/tmp/orig.bam"),
            keyvalues={"asset": "alignment"},
        )
        original_kv = dict(base.keyvalues)
        specialize(base)
        assert base.keyvalues == original_kv
        assert type(base) is Asset
