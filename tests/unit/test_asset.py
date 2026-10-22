"""Tests for Asset base class."""

from pathlib import Path

import pytest
from conftest import FakePublicTier

from stargazer.assets.alignment import Alignment
from stargazer.assets.asset import Asset
from stargazer.assets.reference import Reference, ReferenceIndex


class TestAssetRoundtrip:
    def test_roundtrip_with_path(self):
        original = Alignment(
            cid="Qm" + "a" * 44,
            path=Path("/tmp/test.bam"),
            sample_id="NA12878",
        )
        restored = Alignment.from_dict(original.to_dict())
        assert restored.cid == original.cid
        assert restored.path == original.path
        assert restored.sample_id == original.sample_id

    def test_roundtrip_without_path(self):
        original = Alignment(cid="Qm" + "b" * 44, sample_id="NA12878")
        restored = Alignment.from_dict(original.to_dict())
        assert restored.cid == original.cid
        assert restored.path is None
        assert restored.sample_id == original.sample_id

    def test_roundtrip_empty(self):
        original = Asset()
        restored = Asset.from_dict(original.to_dict())
        assert restored.cid == ""
        assert restored.path is None

    def test_to_dict_structure(self):
        asset = Alignment(cid="abc123", path=Path("/tmp/file.bam"), sample_id="S1")
        data = asset.to_dict()
        assert data["cid"] == "abc123"
        assert data["path"] == "/tmp/file.bam"
        assert data["keyvalues"]["sample_id"] == "S1"
        assert data["keyvalues"]["asset"] == "alignment"

    def test_to_dict_none_path(self):
        asset = Asset(cid="abc123")
        data = asset.to_dict()
        assert data["path"] is None

    def test_from_dict_round_trips_keyvalues(self):
        original = Alignment(cid="xyz", sample_id="S1", duplicates_marked=True)
        restored = Alignment.from_dict(original.to_dict())
        assert restored.sample_id == "S1"
        assert restored.duplicates_marked is True


class TestBareAssetKeyvalues:
    """Bare Asset carries free-form keyvalues verbatim."""

    def test_to_keyvalues_passthrough(self):
        kv = {"asset": "sample_sheet", "sequencer": "novaseq", "lanes": "4"}
        assert Asset(keyvalues=kv).to_keyvalues() == kv

    def test_to_keyvalues_returns_copy(self):
        """Callers (e.g. _owner stamping) may mutate the result freely."""
        asset = Asset(keyvalues={"asset": "sample_sheet"})
        asset.to_keyvalues()["_owner"] = "someone"
        assert "_owner" not in asset.keyvalues

    def test_from_keyvalues_preserves(self):
        kv = {"asset": "sample_sheet", "sequencer": "novaseq"}
        restored = Asset.from_keyvalues(kv, cid="bafy123")
        assert restored.keyvalues == kv
        assert restored.cid == "bafy123"

    def test_to_dict_round_trip(self):
        original = Asset(
            cid="bafy456",
            path=Path("/tmp/sheet.tsv"),
            keyvalues={"asset": "sample_sheet", "sequencer": "novaseq"},
        )
        restored = Asset.from_dict(original.to_dict())
        assert restored.keyvalues == original.keyvalues
        assert restored.cid == original.cid
        assert restored.path == original.path


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


class TestAssetDefaults:
    def test_default_cid_is_empty(self):
        assert Asset().cid == ""

    def test_default_path_is_none(self):
        assert Asset().path is None

    def test_asset_key_in_to_keyvalues(self):
        """Concrete subclasses include 'asset' key in to_keyvalues()."""
        ref = Reference()
        assert ref.to_keyvalues().get("asset") == "reference"

    def test_base_asset_to_keyvalues_empty(self):
        """Base Asset with no _asset_key returns empty dict from to_keyvalues()."""
        assert Asset().to_keyvalues() == {}


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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_fetch_asks_the_public_tier_once(self, ref_files, isolated_storage):
        """One exact-match query per fetch, not one per companion type."""
        fasta, _, _ = ref_files
        ref = Reference()
        await ref.update(fasta, build="T")
        isolated_storage.public = FakePublicTier()

        await ref.fetch()

        assert isolated_storage.public.queries == [{"companion_of": ref.cid}]
