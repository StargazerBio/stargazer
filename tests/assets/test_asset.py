"""Tests for the Asset base class: declared fields, keyvalues, extras, fetch."""

from pathlib import Path

import pytest
from conftest import FakePublicTier

from stargazer.assets.alignment import Alignment
from stargazer.assets.asset import Asset
from stargazer.assets.reads import R1
from stargazer.assets.reference import Reference, ReferenceIndex
from stargazer.assets.variants import Variants

STORED_ALIGNMENT = {
    "asset": "alignment",
    "sample_id": "S1",
    "sorted": "",
    "duplicates_marked": "true",
    "bqsr_applied": "false",
    "tool": "",
    "reference_cid": "",
    "r1_cid": "",
    "lane": "3",
}


class TestDeclaredFields:
    def test_typed_asset_lists_its_own_fields_in_order(self):
        assert R1.declared_fields() == ("sample_id", "mate_cid", "sequencing_platform")

    def test_bare_asset_declares_none(self):
        assert Asset.declared_fields() == ()

    def test_unknown_field_on_a_typed_asset_raises(self):
        with pytest.raises(AttributeError, match="has no field"):
            R1().unknown = "x"

    def test_bare_asset_takes_any_attribute(self):
        a = Asset()
        a.other_key = "fine"
        assert a.other_key == "fine"

    def test_unset_fields_read_as_their_types_empty_value(self):
        assert (Alignment().duplicates_marked, Alignment().sorted) == (False, "")
        assert (Variants().sample_count, Variants().source_samples) == (0, None)


class TestKeyvalues:
    """Fields are stored as strings; non-str ones as JSON."""

    def test_non_str_fields_encode_as_json_and_decode_back(self):
        kv = Variants(sample_count=3, source_samples=["A", "B"]).to_keyvalues()

        assert (kv["sample_count"], kv["source_samples"]) == ("3", '["A", "B"]')
        restored = Variants.from_keyvalues(kv)
        assert (restored.sample_count, restored.source_samples) == (3, ["A", "B"])

    def test_bare_asset_keyvalues_pass_through(self):
        kv = {"asset": "sample_sheet", "sequencer": "novaseq", "lanes": "4"}
        assert Asset(keyvalues=kv).to_keyvalues() == kv
        assert Asset.from_keyvalues(kv, cid="bafy123").keyvalues == kv

    def test_bare_asset_without_keyvalues_has_none(self):
        assert Asset().to_keyvalues() == {}

    def test_to_keyvalues_returns_a_copy(self):
        """Callers (e.g. _owner stamping) may mutate the result freely."""
        asset = Asset(keyvalues={"asset": "sample_sheet"})
        asset.to_keyvalues()["_owner"] = "someone"
        assert "_owner" not in asset.keyvalues


class TestTypedExtras:
    """Typed assets keep undeclared keys as string extras in `keyvalues`."""

    def test_from_keyvalues_splits_declared_and_extra(self):
        aln = Alignment.from_keyvalues(STORED_ALIGNMENT)
        assert (aln.sample_id, aln.duplicates_marked) == ("S1", True)
        assert aln.keyvalues == {"lane": "3"}

    def test_round_trip_is_exact(self):
        assert (
            Alignment.from_keyvalues(STORED_ALIGNMENT).to_keyvalues()
            == STORED_ALIGNMENT
        )

    def test_to_keyvalues_writes_extras_beside_declared_fields(self):
        aln = Alignment(sample_id="S1", duplicates_marked=True, keyvalues={"lane": "3"})
        assert aln.to_keyvalues() == STORED_ALIGNMENT

    def test_declared_field_in_extras_raises(self):
        with pytest.raises(ValueError, match="sample_id"):
            Alignment(keyvalues={"sample_id": "X"}).to_keyvalues()

    def test_asset_key_in_extras_raises(self):
        with pytest.raises(ValueError, match="asset"):
            Alignment(keyvalues={"asset": "x"}).to_keyvalues()


class TestDict:
    """`to_dict()` / `from_dict()`, the shape assets cross the MCP wire in."""

    def test_to_dict_shape(self):
        data = Alignment(
            cid="abc123", path=Path("/tmp/file.bam"), sample_id="S1"
        ).to_dict()
        assert (data["cid"], data["path"]) == ("abc123", "/tmp/file.bam")
        assert data["keyvalues"]["sample_id"] == "S1"
        assert data["keyvalues"]["asset"] == "alignment"

    def test_typed_asset_round_trips(self):
        original = Alignment(
            cid="bafyA",
            path=Path("/tmp/test.bam"),
            sample_id="S1",
            duplicates_marked=True,
            keyvalues={"lane": "3"},
        )
        restored = Alignment.from_dict(original.to_dict())
        assert restored.to_keyvalues() == original.to_keyvalues()
        assert (restored.cid, restored.path) == ("bafyA", original.path)

    def test_bare_asset_round_trips(self):
        original = Asset(
            cid="bafy456",
            path=Path("/tmp/sheet.tsv"),
            keyvalues={"asset": "sample_sheet", "sequencer": "novaseq"},
        )
        restored = Asset.from_dict(original.to_dict())
        assert restored.keyvalues == original.keyvalues
        assert (restored.cid, restored.path) == (original.cid, original.path)

    def test_empty_asset_round_trips_without_a_path(self):
        restored = Asset.from_dict(Asset().to_dict())
        assert (restored.cid, restored.path) == ("", None)


class TestFetch:
    @pytest.fixture
    def ref_files(self, tmp_path):
        """A FASTA, its .fai and a BAM, as local files."""
        fasta = tmp_path / "ref.fa"
        fasta.write_text(">chr1\nACGT\n")
        fai = tmp_path / "ref.fa.fai"
        fai.write_text("chr1\t4\t6\t4\t5\n")
        bam = tmp_path / "s1.bam"
        bam.write_bytes(b"BAM")
        return fasta, fai, bam

    async def test_fetch_brings_companions_not_dependents(self, ref_files):
        """A reference's index lands beside it; an alignment made against it doesn't."""
        fasta, fai, bam = ref_files
        ref = Reference()
        await ref.update(fasta, build="T")
        await ReferenceIndex().update(fai, build="T", companion_of=ref.cid)
        await Alignment().update(bam, sample_id="s1", reference_cid=ref.cid)

        local = await ref.fetch()

        assert sorted(p.name for p in local.parent.iterdir()) == [
            "ref.fa",
            "ref.fa.fai",
        ]

    async def test_fetch_brings_an_untyped_companion(self, ref_files):
        """`companion_of` alone makes a file a companion, with no class for it."""
        fasta, fai, _ = ref_files
        ref = Reference()
        await ref.update(fasta, build="T")
        await Asset(keyvalues={"asset": "my_index", "companion_of": ref.cid}).update(
            fai
        )

        local = await ref.fetch()

        assert (local.parent / "ref.fa.fai").read_text() == "chr1\t4\t6\t4\t5\n"

    async def test_fetch_asks_the_public_tier_once(self, ref_files, isolated_storage):
        """One exact-match query per fetch, not one per companion type."""
        fasta, _, _ = ref_files
        ref = Reference()
        await ref.update(fasta, build="T")
        isolated_storage.public = FakePublicTier()

        await ref.fetch()

        assert isolated_storage.public.queries == [{"companion_of": ref.cid}]
