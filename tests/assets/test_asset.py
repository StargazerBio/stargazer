"""Tests for the Asset base class: declared fields, keyvalues, extras, fetch."""

from pathlib import Path

import pytest
from conftest import FakePublicTier

from stargazer.assets import specialize
from stargazer.assets.alignment import Alignment
from stargazer.assets.asset import Asset
from stargazer.assets.reads import R1
from stargazer.assets.reference import Reference, ReferenceIndex
from stargazer.assets.scrna import AnnData
from stargazer.assets.variants import Variants
from stargazer.utils.cid import compute_cid

STORED_ALIGNMENT = {
    "asset": "alignment",
    "sample_id": "S1",
    "sorted": "",
    "duplicates_marked": "true",
    "bqsr_applied": "false",
    "tool": "",
    "reference_cid": "",
    "source_cid": "",
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
        assert (Variants().source_cids, Variants().source_samples) == (None, None)


class TestKeyvalues:
    """Fields are stored as strings; non-str ones as JSON."""

    def test_non_str_fields_encode_as_json_and_decode_back(self):
        kv = AnnData(n_obs=3).to_keyvalues()

        assert kv["n_obs"] == "3"
        assert AnnData.from_keyvalues(kv).n_obs == 3

    def test_source_cids_encode_as_a_json_array_and_round_trip(self):
        kv = Variants(source_cids=["a", "b"]).to_keyvalues()

        assert kv["source_cids"] == '["a", "b"]'
        assert Variants.from_keyvalues(kv).source_cids == ["a", "b"]

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
    """`to_dict()` is the storage record shape, which `specialize()` reads back."""

    def test_to_dict_is_the_record_shape(self):
        data = Alignment(
            cid="abc123", path=Path("/tmp/file.bam"), sample_id="S1"
        ).to_dict()
        assert set(data) == {"cid", "uri", "name", "keyvalues"}
        assert (data["cid"], data["uri"], data["name"]) == (
            "abc123",
            "/tmp/file.bam",
            "file.bam",
        )
        assert data["keyvalues"]["sample_id"] == "S1"
        assert data["keyvalues"]["asset"] == "alignment"

    def test_typed_asset_round_trips_through_specialize(self):
        original = Alignment(
            cid="bafyA",
            path=Path("/tmp/test.bam"),
            sample_id="S1",
            duplicates_marked=True,
            keyvalues={"lane": "3"},
        )
        restored = specialize(original.to_dict())
        assert type(restored) is Alignment
        assert restored.to_keyvalues() == original.to_keyvalues()
        assert (restored.cid, restored.path.path, restored.path.name) == (
            "bafyA",
            "/tmp/test.bam",
            "test.bam",
        )

    def test_bare_asset_round_trips_through_specialize(self):
        original = Asset(
            cid="bafy456",
            path=Path("/tmp/sheet.tsv"),
            keyvalues={"asset": "sample_sheet", "sequencer": "novaseq"},
        )
        restored = specialize(original.to_dict())
        assert type(restored) is Asset
        assert restored.keyvalues == original.keyvalues
        assert (restored.cid, restored.path.path) == ("bafy456", "/tmp/sheet.tsv")

    def test_empty_asset_has_no_uri(self):
        data = Asset().to_dict()
        assert (data["cid"], data["uri"], data["name"]) == ("", None, None)
        assert specialize(data).path is None


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
        ref = await Reference.store(fasta, build="T")
        await ReferenceIndex.store(fai, build="T", companion_of=ref.cid)
        await Alignment.store(bam, sample_id="s1", reference_cid=ref.cid)

        local = await ref.fetch()

        assert sorted(p.name for p in local.parent.iterdir()) == [
            "ref.fa",
            "ref.fa.fai",
        ]

    async def test_fetch_brings_an_untyped_companion(self, ref_files):
        """`companion_of` alone makes a file a companion, with no class for it."""
        fasta, fai, _ = ref_files
        ref = await Reference.store(fasta, build="T")
        await Asset.store(fai, keyvalues={"asset": "my_index", "companion_of": ref.cid})

        local = await ref.fetch()

        assert (local.parent / "ref.fa.fai").read_text() == "chr1\t4\t6\t4\t5\n"

    async def test_fetch_asks_the_public_tier_once(self, ref_files, isolated_storage):
        """One exact-match query per fetch, not one per companion type."""
        fasta, _, _ = ref_files
        ref = await Reference.store(fasta, build="T")
        isolated_storage.public = FakePublicTier()

        await ref.fetch()

        assert isolated_storage.public.queries == [{"companion_of": ref.cid}]


async def test_store_uploads_and_returns_the_typed_asset(tmp_path):
    """`store` builds the asset from its fields, uploads the file and returns it."""
    fasta = tmp_path / "ref.fa"
    fasta.write_bytes(b">chr1\nACGT\n")

    ref = await Reference.store(fasta, build="T")

    assert isinstance(ref, Reference)
    assert ref.build == "T"
    assert ref.cid == compute_cid(fasta)
    assert (await ref.fetch()).read_bytes() == b">chr1\nACGT\n"


async def test_store_refuses_an_undeclared_field(tmp_path):
    """A field the type doesn't declare raises, as it does on assignment."""
    fasta = tmp_path / "ref.fa"
    fasta.write_bytes(b">chr1\nACGT\n")

    with pytest.raises(AttributeError, match="no field 'lane'"):
        await Reference.store(fasta, build="T", lane="3")


async def test_store_names_a_missing_file(tmp_path):
    """Storing a file that isn't there raises `FileNotFoundError` naming it."""
    with pytest.raises(FileNotFoundError, match="absent.fa"):
        await Reference.store(tmp_path / "absent.fa", build="T")
