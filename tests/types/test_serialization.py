"""Roundtrip serialization tests for to_dict() / from_dict() on all types."""

from stargazer.types.component import ComponentFile
from stargazer.types.reference import (
    Reference,
    ReferenceFile,
    ReferenceIndex,
    SequenceDict,
    AlignerIndex,
)
from stargazer.types.alignment import Alignment, AlignmentFile, AlignmentIndex
from stargazer.types.reads import Reads, R1File, R2File
from stargazer.types.variants import Variants, VariantsFile, VariantsIndex


class TestComponentFileRoundtrip:
    def test_roundtrip(self):
        original = ComponentFile(
            cid="Qm" + "a" * 44,
            keyvalues={"type": "reference", "component": "fasta"},
        )
        data = original.to_dict()
        restored = ComponentFile.from_dict(data)

        assert restored.cid == original.cid
        assert restored.path is None
        assert restored.keyvalues == original.keyvalues

    def test_roundtrip_public(self):
        original = ComponentFile(cid="abc", keyvalues={"public": "true"})
        restored = ComponentFile.from_dict(original.to_dict())
        assert restored.keyvalues.get("public") == "true"

    def test_roundtrip_none_path(self):
        original = ComponentFile(cid="xyz")
        restored = ComponentFile.from_dict(original.to_dict())
        assert restored.path is None


class TestReferenceRoundtrip:
    def test_minimal(self):
        original = Reference(build="GRCh38")
        restored = Reference.from_dict(original.to_dict())
        assert restored.build == "GRCh38"
        assert restored.fasta is None
        assert restored.faidx is None
        assert restored.sequence_dictionary is None
        assert restored.aligner_index == []

    def test_full(self):
        original = Reference(
            build="GRCh38",
            fasta=ReferenceFile(cid="fasta-1", keyvalues={"build": "GRCh38"}),
            faidx=ReferenceIndex(cid="faidx-1", keyvalues={"build": "GRCh38"}),
            sequence_dictionary=SequenceDict(
                cid="dict-1", keyvalues={"build": "GRCh38"}
            ),
            aligner_index=[
                AlignerIndex(
                    cid=f"idx-{i}", keyvalues={"build": "GRCh38", "aligner": "bwa"}
                )
                for i in range(5)
            ],
        )
        restored = Reference.from_dict(original.to_dict())

        assert restored.build == original.build
        assert restored.fasta.cid == "fasta-1"
        assert restored.fasta.build == "GRCh38"
        assert restored.faidx.cid == "faidx-1"
        assert restored.sequence_dictionary.cid == "dict-1"
        assert len(restored.aligner_index) == 5
        assert restored.aligner_index[2].cid == "idx-2"
        assert restored.aligner_index[0].aligner == "bwa"


class TestAlignmentRoundtrip:
    def test_minimal(self):
        original = Alignment(sample_id="NA12878")
        restored = Alignment.from_dict(original.to_dict())
        assert restored.sample_id == "NA12878"
        assert restored.alignment is None
        assert restored.index is None

    def test_full(self):
        original = Alignment(
            sample_id="NA12878",
            alignment=AlignmentFile(
                cid="aln-1",
                keyvalues={
                    "sorted": "coordinate",
                    "duplicates_marked": "true",
                    "bqsr_applied": "true",
                },
            ),
            index=AlignmentIndex(cid="idx-1"),
        )
        data = original.to_dict()
        restored = Alignment.from_dict(data)

        assert restored.sample_id == "NA12878"
        assert restored.alignment.cid == "aln-1"
        assert restored.index.cid == "idx-1"
        assert restored.alignment.sorted == "coordinate"
        assert restored.alignment.duplicates_marked is True
        assert restored.alignment.bqsr_applied is True

    def test_component_metadata_in_dict(self):
        """Alignment metadata is now inside the component's keyvalues."""
        original = Alignment(
            sample_id="S1",
            alignment=AlignmentFile(keyvalues={"sorted": "coordinate"}),
        )
        data = original.to_dict()
        # Metadata lives in the component dict's keyvalues
        assert data["alignment"]["keyvalues"]["sorted"] == "coordinate"
        # Not at the top level anymore
        assert "is_sorted" not in data
        assert "has_duplicates_marked" not in data


class TestReadsRoundtrip:
    def test_minimal(self):
        original = Reads(sample_id="NA12878")
        restored = Reads.from_dict(original.to_dict())
        assert restored.sample_id == "NA12878"
        assert restored.r1 is None
        assert restored.r2 is None
        assert restored.read_group is None

    def test_paired(self):
        original = Reads(
            sample_id="NA12878",
            r1=R1File(cid="r1-1", keyvalues={"sequencing_platform": "ILLUMINA"}),
            r2=R2File(cid="r2-1"),
            read_group={"ID": "rg1", "SM": "NA12878", "PL": "ILLUMINA"},
        )
        data = original.to_dict()
        assert data["is_paired"] is True

        restored = Reads.from_dict(data)
        assert restored.sample_id == "NA12878"
        assert restored.r1.cid == "r1-1"
        assert restored.r2.cid == "r2-1"
        assert restored.read_group == {"ID": "rg1", "SM": "NA12878", "PL": "ILLUMINA"}
        assert restored.is_paired is True
        assert restored.r1.sequencing_platform == "ILLUMINA"

    def test_single_end(self):
        original = Reads(sample_id="S1", r1=R1File(cid="r1-only"))
        data = original.to_dict()
        assert data["is_paired"] is False

        restored = Reads.from_dict(data)
        assert restored.r1.cid == "r1-only"
        assert restored.r2 is None
        assert restored.is_paired is False


class TestVariantsRoundtrip:
    def test_minimal(self):
        original = Variants(sample_id="NA12878")
        restored = Variants.from_dict(original.to_dict())
        assert restored.sample_id == "NA12878"
        assert restored.vcf is None
        assert restored.index is None

    def test_full(self):
        original = Variants(
            sample_id="NA12878",
            vcf=VariantsFile(
                cid="vcf-1",
                keyvalues={
                    "caller": "haplotypecaller",
                    "variant_type": "gvcf",
                    "sample_count": "1",
                },
            ),
            index=VariantsIndex(cid="tbi-1"),
        )
        data = original.to_dict()

        restored = Variants.from_dict(data)
        assert restored.sample_id == "NA12878"
        assert restored.vcf.cid == "vcf-1"
        assert restored.index.cid == "tbi-1"
        assert restored.vcf.caller == "haplotypecaller"
        assert restored.vcf.variant_type == "gvcf"
        assert restored.vcf.sample_count == 1

    def test_component_metadata_in_dict(self):
        """Variants metadata is now inside the component's keyvalues."""
        original = Variants(
            sample_id="S1",
            vcf=VariantsFile(
                keyvalues={"caller": "deepvariant", "variant_type": "gvcf"}
            ),
        )
        data = original.to_dict()
        # Metadata lives in the component dict's keyvalues
        assert data["vcf"]["keyvalues"]["caller"] == "deepvariant"
        # Not at the top level anymore
        assert "caller" not in data
        assert "is_gvcf" not in data

    def test_multi_sample(self):
        original = Variants(
            sample_id="cohort",
            vcf=VariantsFile(
                keyvalues={
                    "sample_count": "3",
                    "source_samples": "S1,S2,S3",
                },
            ),
        )
        data = original.to_dict()
        restored = Variants.from_dict(data)
        assert restored.vcf.sample_count == 3
        assert restored.vcf.source_samples == ["S1", "S2", "S3"]
