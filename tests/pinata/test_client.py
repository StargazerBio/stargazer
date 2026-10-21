"""
Test for Pinata file upload, deletion, and querying using real API.

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
    "GRCh38_TP53.fa.fai": "bafkreic2oy3e2m3fbloj46epkpbpvrobresfkreuojhofnxiiwhz67xntq",
    "GRCh38_TP53.fa.amb": "bafkreick7eyrefagckncfqcw5t6t2uudkeme74mztgt6edp2mv6qamh4y4",
    "GRCh38_TP53.fa.ann": "bafkreibitlcqn3x52lmb7kngovaaz3qp4ckihtylvmcmvuejoya7ntv4tu",
    "GRCh38_TP53.fa.bwt": "bafkreigmugdxgf4lcczuws6rvgy7ufl24twf3kdgilwv2rtiyq5iwdyu7i",
    "GRCh38_TP53.fa.pac": "bafkreicouoxr5idj6ohh56bxxxuhwk7sjhrvk7xai5blczw762ny6t4eoy",
    "GRCh38_TP53.fa.sa": "bafkreic2h3ct6sqgiaqjmqyuwlvmja6iujaauqs3lqgl3miflgks4nkzae",
    "upload_delete.txt": "bafkreigaquk2gy7m3mojfzsmlu3s7kz6ya5buruzrwowmcuh5tna7vyx34",
}


@pytest.mark.asyncio
async def test_upload_and_delete_file():
    """Test uploading a file to Pinata and then deleting it."""
    client = PinataClient()

    test_file_path = FIXTURES_DIR.joinpath("upload_delete.txt")
    assert test_file_path.exists(), f"Test file not found: {test_file_path}"

    print(f"\nUploading test file: {test_file_path.name}")
    comp = Asset()
    await client.upload(comp, test_file_path)

    try:
        assert comp.cid, "Upload should return a CID"
        print(f"Upload successful - CID: {comp.cid}")

        expected_cid = CIDS.get("upload_delete.txt")
        if expected_cid:
            assert comp.cid == expected_cid, (
                f"CID mismatch: expected {expected_cid}, got {comp.cid}"
            )
            print("CID matches expected value")
        else:
            print(f"  Note: Add to CIDS: 'upload_delete.txt': '{comp.cid}'")

    finally:
        try:
            await client.delete(Asset(cid=comp.cid))
        except Exception as exc:
            print(f"Cleanup skipped (Pinata post-upload delay?): {exc}")


@pytest.mark.asyncio
async def test_tus_upload_multichunk_roundtrip(tmp_path, monkeypatch):
    """Force the TUS path on a small file with a tiny chunk size so the
    offset loop runs several PATCHes, then check Pinata's CID matches the
    one computed locally — a broken offset loop corrupts the bytes and so
    the CID.
    """
    import stargazer.utils.pinata as pinata_mod

    # Force TUS regardless of size, and chunk small enough to loop.
    monkeypatch.setattr(pinata_mod, "TUS_THRESHOLD_BYTES", 0)
    monkeypatch.setattr(pinata_mod, "TUS_CHUNK_BYTES", 4096)

    remote = PinataClient()
    content = b"".join(f"stargazer tus line {i}\n".encode() for i in range(2000))
    src = tmp_path / "tus_roundtrip.txt"
    src.write_bytes(content)

    comp = Asset(keyvalues={"asset": "never_registered_key"})
    await remote.upload(comp, src)
    assert comp.cid, "TUS upload should set the cid (from Upload-Cid header)"

    try:
        assert comp.cid == compute_cid(src), "TUS reassembly corrupted bytes"
    finally:
        try:
            await remote.delete(Asset(cid=comp.cid))
        except Exception as exc:
            print(f"cleanup skipped: {exc}")


@pytest.mark.asyncio
async def test_create_signed_upload_url_end_to_end(tmp_path):
    """Mint a signed upload URL, upload bytes to it like a browser would,
    and verify the mint-time metadata reached the stored record.

    Also probes (informationally, no assert — undocumented semantics) what
    a second upload to the same URL does, answering plan 20's open
    single-use question.
    """
    import aiohttp

    client = PinataClient()

    url = await client.create_signed_upload_url(
        filename="signed_upload_test.txt",
        keyvalues={
            "asset": "never_registered_key",
            "purpose": "signed-url-test",
            "_owner": "integration-test",
        },
        expires=120,
        max_file_size=1024,
    )
    assert url.startswith("https://"), f"Unexpected signed URL: {url!r}"
    print(f"\nSigned URL minted: {url[:80]}...")

    test_file = tmp_path / "signed_upload_test.txt"
    test_file.write_text("stargazer signed upload test\n")

    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("file", test_file.open("rb"), filename=test_file.name)
        async with session.post(url, data=data) as resp:
            body = await resp.json()
            assert resp.status in (200, 201), f"Upload failed: {resp.status} {body}"

    record = body.get("data", body)
    cid = record.get("cid")
    assert cid, f"Upload response carries no cid: {body}"
    print(f"Upload response cid: {cid}")
    print(f"Upload response keyvalues: {record.get('keyvalues')}")

    try:
        # Mint-time metadata must be on the stored record (the whole point
        # of the signed-URL design: the uploader can't choose keyvalues).
        assert record.get("keyvalues", {}).get("purpose") == "signed-url-test"
        assert record.get("keyvalues", {}).get("_owner") == "integration-test"
        assert record.get("name") == "signed_upload_test.txt"

        # Single-use probe: second upload to the same URL.
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", test_file.open("rb"), filename=test_file.name)
            async with session.post(url, data=data) as resp:
                print(f"Second upload to same signed URL: HTTP {resp.status}")
    finally:
        try:
            await client.delete(Asset(cid=cid))
            print(f"Cleaned up {cid}")
        except Exception as exc:
            print(f"Cleanup skipped (Pinata post-upload delay?): {exc}")


@pytest.mark.asyncio
async def test_update_metadata_merges(tmp_path):
    """Update metadata on an existing public file and verify Pinata MERGES.

    Uploads a probe with two keyvalues, PUTs a patch that changes one and
    adds a new key, then re-queries: the untouched key must survive (merge,
    not replace) and the CID must be unchanged (metadata edit doesn't touch
    bytes). Cleans up regardless.
    """
    import aiohttp

    client = PinataClient()

    url = await client.create_signed_upload_url(
        filename="update_meta_test.txt",
        keyvalues={"asset": "never_registered_key", "stage": "before", "keep": "me"},
        expires=120,
        max_file_size=1024,
    )
    test_file = tmp_path / "update_meta_test.txt"
    test_file.write_text("update metadata test\n")
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("file", test_file.open("rb"), filename=test_file.name)
        async with session.post(url, data=data) as resp:
            cid = (await resp.json())["data"]["cid"]

    try:
        result = await client.update_metadata(
            cid,
            {"asset": "never_registered_key", "stage": "after", "added": "yes"},
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
async def test_upload_at_the_keyvalue_cap(tmp_path, monkeypatch):
    """An R1 with four extras stamps to exactly 9 keys, and all 9 come back."""
    monkeypatch.setenv("STARGAZER_OWNER", "integration-test")
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
async def test_upload_over_the_keyvalue_cap_stores_nothing(tmp_path, monkeypatch):
    """One key past the cap is refused before anything is sent."""
    monkeypatch.setenv("STARGAZER_OWNER", "integration-test")
    tag = uuid.uuid4().hex
    client = PinataClient()
    extras = {"probe": tag, "x0": "v", "x1": "v", "x2": "v", "x3": "v"}
    r1 = R1(sample_id="S1", keyvalues=extras)

    with pytest.raises(ValueError, match="at most 9 .* has 10"):
        await client.upload(r1, _unique_file(tmp_path, tag))

    assert r1.cid == ""
    assert await client.query({"probe": tag}) == []


@pytest.mark.asyncio
async def test_alignment_uploads_with_every_field_and_owner(tmp_path, monkeypatch):
    """An Alignment with all its fields set, plus _owner, fits the cap."""
    monkeypatch.setenv("STARGAZER_OWNER", "integration-test")
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
async def test_publish_puts_a_stored_asset_on_the_public_network(tmp_path, monkeypatch):
    """A stored asset published keeps its CID and keyvalues on Pinata."""
    monkeypatch.setenv("STARGAZER_OWNER", "integration-test")
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
