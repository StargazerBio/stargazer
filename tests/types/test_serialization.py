"""Roundtrip serialization tests for to_dict() / from_dict() on all types."""

from datetime import datetime, timezone

from stargazer.utils.pinata import IpFile
from stargazer.types import Reference, Alignment, Reads, Variants


def _make_ipfile(**overrides) -> IpFile:
    defaults = {
        "id": "file-001",
        "cid": "Qm" + "a" * 44,
        "name": "test.fa",
        "size": 1024,
        "keyvalues": {"type": "reference", "component": "fasta"},
        "created_at": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        "is_public": False,
    }
    defaults.update(overrides)
    return IpFile(**defaults)


class TestIpFileRoundtrip:
    def test_roundtrip(self):
        original = _make_ipfile()
        data = original.to_dict()
        restored = IpFile.from_dict(data)

        assert restored.id == original.id
        assert restored.cid == original.cid
        assert restored.name == original.name
        assert restored.size == original.size
        assert restored.keyvalues == original.keyvalues
        assert restored.created_at == original.created_at
        assert restored.is_public == original.is_public

    def test_roundtrip_public(self):
        original = _make_ipfile(is_public=True)
        restored = IpFile.from_dict(original.to_dict())
        assert restored.is_public is True

    def test_roundtrip_none_name(self):
        original = _make_ipfile(name=None)
        restored = IpFile.from_dict(original.to_dict())
        assert restored.name is None


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
            fasta=_make_ipfile(id="fasta-1", name="ref.fa"),
            faidx=_make_ipfile(id="faidx-1", name="ref.fa.fai"),
            sequence_dictionary=_make_ipfile(id="dict-1", name="ref.dict"),
            aligner_index=[
                _make_ipfile(id=f"idx-{i}", name=f"ref.{ext}")
                for i, ext in enumerate(["amb", "ann", "bwt", "pac", "sa"])
            ],
        )
        restored = Reference.from_dict(original.to_dict())

        assert restored.build == original.build
        assert restored.fasta.id == "fasta-1"
        assert restored.faidx.id == "faidx-1"
        assert restored.sequence_dictionary.id == "dict-1"
        assert len(restored.aligner_index) == 5
        assert restored.aligner_index[2].name == "ref.bwt"


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
            alignment=_make_ipfile(
                id="aln-1",
                name="sorted.bam",
                keyvalues={
                    "sorted": "coordinate",
                    "duplicates_marked": "true",
                    "bqsr_applied": "true",
                },
            ),
            index=_make_ipfile(id="idx-1", name="sorted.bam.bai"),
        )
        data = original.to_dict()
        restored = Alignment.from_dict(data)

        assert restored.sample_id == "NA12878"
        assert restored.alignment.id == "aln-1"
        assert restored.index.id == "idx-1"
        assert restored.is_sorted is True
        assert restored.has_duplicates_marked is True
        assert restored.has_bqsr_applied is True

    def test_derived_fields_in_dict(self):
        original = Alignment(
            sample_id="S1",
            alignment=_make_ipfile(keyvalues={"sorted": "coordinate"}),
        )
        data = original.to_dict()
        assert data["is_sorted"] is True
        assert data["has_duplicates_marked"] is False
        assert data["has_bqsr_applied"] is False


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
            r1=_make_ipfile(id="r1-1", name="R1.fastq.gz"),
            r2=_make_ipfile(id="r2-1", name="R2.fastq.gz"),
            read_group={"ID": "rg1", "SM": "NA12878", "PL": "ILLUMINA"},
        )
        data = original.to_dict()
        assert data["is_paired"] is True

        restored = Reads.from_dict(data)
        assert restored.sample_id == "NA12878"
        assert restored.r1.id == "r1-1"
        assert restored.r2.id == "r2-1"
        assert restored.read_group == {"ID": "rg1", "SM": "NA12878", "PL": "ILLUMINA"}
        assert restored.is_paired is True

    def test_single_end(self):
        original = Reads(
            sample_id="S1",
            r1=_make_ipfile(id="r1-only"),
        )
        data = original.to_dict()
        assert data["is_paired"] is False

        restored = Reads.from_dict(data)
        assert restored.r1.id == "r1-only"
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
            vcf=_make_ipfile(
                id="vcf-1",
                name="variants.g.vcf.gz",
                keyvalues={
                    "caller": "haplotypecaller",
                    "variant_type": "gvcf",
                    "sample_count": "1",
                },
            ),
            index=_make_ipfile(id="tbi-1", name="variants.g.vcf.gz.tbi"),
        )
        data = original.to_dict()
        assert data["caller"] == "haplotypecaller"
        assert data["is_gvcf"] is True
        assert data["is_multi_sample"] is False

        restored = Variants.from_dict(data)
        assert restored.sample_id == "NA12878"
        assert restored.vcf.id == "vcf-1"
        assert restored.index.id == "tbi-1"
        assert restored.caller == "haplotypecaller"
        assert restored.is_gvcf is True

    def test_multi_sample(self):
        original = Variants(
            sample_id="cohort",
            vcf=_make_ipfile(
                keyvalues={
                    "sample_count": "3",
                    "source_samples": "S1,S2,S3",
                },
            ),
        )
        data = original.to_dict()
        assert data["is_multi_sample"] is True
        assert data["source_samples"] == ["S1", "S2", "S3"]

        restored = Variants.from_dict(data)
        assert restored.is_multi_sample is True
        assert restored.source_samples == ["S1", "S2", "S3"]
