"""Tests for ComponentFile specialization."""

from pathlib import Path

from stargazer.types.component import ComponentFile
from stargazer.types import specialize
from stargazer.types.reference import (
    ReferenceFile,
    ReferenceIndex,
    SequenceDict,
    AlignerIndex,
)
from stargazer.types.alignment import AlignmentFile, AlignmentIndex
from stargazer.types.variants import VariantsFile, VariantsIndex
from stargazer.types.reads import R1File, R2File


class TestSpecialize:
    """specialize() converts a base ComponentFile to the correct derived type."""

    def test_reference_fasta(self):
        base = ComponentFile(
            cid="Qmfasta",
            path=Path("/tmp/ref.fa"),
            keyvalues={"type": "reference", "component": "fasta", "build": "GRCh38"},
        )
        result = specialize(base)
        assert type(result) is ReferenceFile
        assert result.cid == "Qmfasta"
        assert result.path == Path("/tmp/ref.fa")
        assert result.build == "GRCh38"

    def test_reference_faidx(self):
        base = ComponentFile(
            cid="Qmfaidx",
            keyvalues={"type": "reference", "component": "faidx", "build": "T2T"},
        )
        result = specialize(base)
        assert type(result) is ReferenceIndex
        assert result.build == "T2T"

    def test_reference_sequence_dictionary(self):
        base = ComponentFile(
            cid="Qmdict",
            keyvalues={"type": "reference", "component": "sequence_dictionary"},
        )
        result = specialize(base)
        assert type(result) is SequenceDict

    def test_reference_aligner_index(self):
        base = ComponentFile(
            cid="Qmaln",
            keyvalues={
                "type": "reference",
                "component": "aligner_index",
                "aligner": "bwa",
            },
        )
        result = specialize(base)
        assert type(result) is AlignerIndex
        assert result.aligner == "bwa"

    def test_alignment_file(self):
        base = ComponentFile(
            cid="Qmbam",
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": "NA12878",
                "duplicates_marked": "true",
                "bqsr_applied": "false",
            },
        )
        result = specialize(base)
        assert type(result) is AlignmentFile
        assert result.sample_id == "NA12878"
        assert result.duplicates_marked is True
        assert result.bqsr_applied is False

    def test_alignment_index(self):
        base = ComponentFile(
            cid="Qmbai",
            keyvalues={"type": "alignment", "component": "index", "sample_id": "S1"},
        )
        result = specialize(base)
        assert type(result) is AlignmentIndex

    def test_variants_vcf(self):
        base = ComponentFile(
            cid="Qmvcf",
            keyvalues={
                "type": "variants",
                "component": "vcf",
                "sample_id": "S1",
                "sample_count": "3",
                "source_samples": "S1,S2,S3",
            },
        )
        result = specialize(base)
        assert type(result) is VariantsFile
        assert result.sample_count == 3
        assert result.source_samples == ["S1", "S2", "S3"]

    def test_variants_index(self):
        base = ComponentFile(
            cid="Qmtbi",
            keyvalues={"type": "variants", "component": "index"},
        )
        result = specialize(base)
        assert type(result) is VariantsIndex

    def test_reads_r1(self):
        base = ComponentFile(
            cid="Qmr1",
            keyvalues={"type": "reads", "component": "r1", "sample_id": "S1"},
        )
        result = specialize(base)
        assert type(result) is R1File

    def test_reads_r2(self):
        base = ComponentFile(
            cid="Qmr2",
            keyvalues={"type": "reads", "component": "r2", "sample_id": "S1"},
        )
        result = specialize(base)
        assert type(result) is R2File

    def test_unknown_type_returns_base(self):
        """Unknown type/component combos return the original ComponentFile."""
        base = ComponentFile(
            cid="Qmunk",
            keyvalues={"type": "unknown", "component": "thing"},
        )
        result = specialize(base)
        assert result is base

    def test_missing_keyvalues_returns_base(self):
        """ComponentFile with no type/component returns itself."""
        base = ComponentFile(cid="Qmbare")
        result = specialize(base)
        assert result is base

    def test_already_specialized_is_idempotent(self):
        """Calling specialize on an already-derived instance returns a new instance of the same type."""
        original = AlignmentFile(
            cid="Qmbam",
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": "S1",
            },
        )
        result = specialize(original)
        assert type(result) is AlignmentFile
        assert result.cid == original.cid

    def test_preserves_all_keyvalues(self):
        """Extra keyvalues beyond type/component are preserved."""
        base = ComponentFile(
            cid="Qm123",
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": "NA12878",
                "custom_field": "custom_value",
            },
        )
        result = specialize(base)
        assert result.keyvalues["custom_field"] == "custom_value"

    def test_does_not_mutate_original(self):
        """The original ComponentFile is not modified."""
        base = ComponentFile(
            cid="Qmorig",
            path=Path("/tmp/orig.bam"),
            keyvalues={"type": "alignment", "component": "alignment"},
        )
        original_kv = dict(base.keyvalues)
        specialize(base)
        assert base.keyvalues == original_kv
        assert type(base) is ComponentFile
