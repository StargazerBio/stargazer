"""
Tests for Pinata uploads, queries, edits and deletes against the real API.

The JWT comes from tests/.secrets/pinata_jwt (this directory's conftest).

To populate expected CIDs for test files, run:
    uv run python cli/upload_to_pinata.py tests/fixtures/general/FILE -m asset=reference --update-config
"""

import uuid

import pytest
from conftest import FIXTURES_DIR

from stargazer.assets import R1, Alignment
from stargazer.assets.asset import Asset
from stargazer.utils.cid import compute_cid
from stargazer.utils.index import SqliteIndex
from stargazer.utils.pinata import PinataClient
from stargazer.utils.storage import StorageClient

CIDS = {
    "GRCh38_TP53.fa": "bafkreib6vj3os7l4lqqytaw5vju46iorcknttfiwfnlbizjcqn7xd5hrvy",
}


@pytest.mark.asyncio
async def test_update_metadata_merges(tmp_path):
    """Update metadata on an existing public file and verify Pinata MERGES.

    Uploads a probe with two keyvalues, PUTs a patch that changes one and
    adds a new key, then re-queries: the untouched key must survive (merge,
    not replace) and the CID must be unchanged (metadata edit doesn't touch
    bytes). Cleans up regardless.
    """
    client = PinataClient()

    test_file = tmp_path / "update_meta_test.txt"
    test_file.write_text(f"update metadata test {uuid.uuid4()}\n")
    probe = Asset(
        keyvalues={"asset": "never_registered_key", "stage": "before", "keep": "me"}
    )
    await client.upload(probe, test_file)
    cid = probe.cid

    try:
        result = await client.update_metadata(
            cid,
            {
                "asset": "never_registered_key",
                "stage": "after",
                "added": "yes",
                "_owner": "integration-test",
            },
        )
        assert result["cid"] == cid, "metadata edit must not change the CID"

        found = await client.query({"asset": "never_registered_key"})
        rec = next((r for r in found if r["cid"] == cid), None)
        assert rec is not None, "updated record should still be queryable"
        kv = rec["keyvalues"]
        assert kv["stage"] == "after", "changed key not applied"
        assert kv["added"] == "yes", "new key not added"
        assert kv["keep"] == "me", (
            "untouched key wiped — update REPLACED, expected MERGE"
        )
    finally:
        try:
            await client.delete(Asset(cid=cid))
        except Exception as exc:
            print(f"Cleanup skipped: {exc}")


@pytest.mark.asyncio
async def test_query():
    """Query Pinata by keyvalues and verify the filter narrows to the right file.

    Uses the build=GRCh38_TP53 keyvalue to pin the result to exactly one file —
    if the filter is being ignored, this returns more than one and fails.
    """
    client = PinataClient()

    expected_cid = CIDS["GRCh38_TP53.fa"]

    found = await client.query({"asset": "reference", "build": "GRCh38_TP53"})

    assert len(found) == 1, (
        f"Expected exactly 1 file matching build=GRCh38_TP53, got {len(found)}: {found}"
    )
    assert found[0]["cid"] == expected_cid, (
        f"CID mismatch: expected {expected_cid}, got {found[0]['cid']}"
    )


@pytest.mark.asyncio
async def test_get_finds_one_public_file_by_cid():
    """`get` returns the record for a published CID, and None for one nobody published."""
    client = PinataClient()

    found = await client.get(CIDS["GRCh38_TP53.fa"])
    missing = await client.get(compute_cid(FIXTURES_DIR / "upload_delete.txt") + "x")

    assert found["cid"] == CIDS["GRCh38_TP53.fa"]
    assert found["keyvalues"]["build"] == "GRCh38_TP53"
    assert missing is None


def _unique_file(tmp_path, tag: str):
    """A small file with bytes no other run has uploaded, and the tag in them.

    Fresh bytes give a fresh CID, so Pinata can't hand back an older record.
    """
    path = tmp_path / f"{tag}.txt"
    path.write_text(f"stargazer keyvalue cap {tag}\n")
    return path


@pytest.mark.asyncio
async def test_upload_at_the_keyvalue_cap(tmp_path):
    """An R1 with four extras stamps to exactly 9 keys, and all 9 come back."""
    tag = uuid.uuid4().hex
    client = PinataClient()
    extras = {"probe": tag, "x0": "v", "x1": "v", "x2": "v"}
    r1 = R1(sample_id="S1", keyvalues=extras)

    await client.upload(r1, _unique_file(tmp_path, tag))

    try:
        [rec] = await client.query({"probe": tag})
        assert rec["keyvalues"] == {**r1.to_keyvalues(), "_owner": "integration-test"}
        assert len(rec["keyvalues"]) == 9
    finally:
        await client.delete(Asset(cid=r1.cid))


@pytest.mark.asyncio
async def test_upload_over_the_keyvalue_cap_stores_nothing(tmp_path):
    """One key past the cap is refused before anything is sent."""
    tag = uuid.uuid4().hex
    client = PinataClient()
    extras = {"probe": tag, "x0": "v", "x1": "v", "x2": "v", "x3": "v"}
    r1 = R1(sample_id="S1", keyvalues=extras)

    with pytest.raises(ValueError, match="at most 9 .* has 10"):
        await client.upload(r1, _unique_file(tmp_path, tag))

    assert r1.cid == ""
    assert await client.query({"probe": tag}) == []


@pytest.mark.asyncio
async def test_alignment_uploads_with_every_field_and_owner(tmp_path):
    """An Alignment with all its fields set, plus _owner, fits the cap."""
    tag = uuid.uuid4().hex
    client = PinataClient()
    aln = Alignment(
        sample_id=tag,
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=True,
        tool="gatk_apply_bqsr",
        reference_cid="bafyref",
        r1_cid="bafyr1",
    )

    await client.upload(aln, _unique_file(tmp_path, tag))

    try:
        [rec] = await client.query({"sample_id": tag})
        assert rec["keyvalues"] == {**aln.to_keyvalues(), "_owner": "integration-test"}
        assert len(rec["keyvalues"]) == 9
    finally:
        await client.delete(Asset(cid=aln.cid))


@pytest.mark.asyncio
async def test_publish_puts_a_stored_asset_on_the_public_network(tmp_path):
    """A stored asset published keeps its CID and keyvalues on Pinata."""
    tag = uuid.uuid4().hex
    client = StorageClient(
        local_dir=tmp_path / "cache",
        store_root=str(tmp_path / "store"),
        index=SqliteIndex(tmp_path / "index.db"),
        public=PinataClient(),
    )
    stored = Asset(keyvalues={"asset": "publish_probe", "tag": tag})
    await client.upload(stored, _unique_file(tmp_path, tag))

    record = await client.publish(stored.cid)

    try:
        assert record["cid"] == stored.cid
        [rec] = await client.public.query({"tag": tag})
        assert rec["cid"] == stored.cid
        assert rec["keyvalues"] == {
            "asset": "publish_probe",
            "tag": tag,
            "_owner": "integration-test",
        }
    finally:
        await client.public.delete(Asset(cid=stored.cid))
