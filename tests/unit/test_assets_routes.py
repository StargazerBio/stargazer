"""Tests for the asset-manager API routes (plan 20, piece 2).

Route tests mount the router on a bare FastAPI app: the dashboard's owner
gate (tested in `test_app.py`) sits in front of these routes there, and is
not what's under test here. Identity comes from the `X-User-Subject`
header Union's auth layer sets on every request. The Pinata client is swapped for a fake via the
`app.assets._pinata_client` module attribute — sign returns a canned URL,
query returns canned records, and both capture their call args. Sign runs
the real client's keyvalue-count check, which happens before any request.

Auth model: public browsing (schema, list, download) is anonymous — public
bytes are world-readable on IPFS anyway, and the listing is served from an
in-process TTL cache so the admin is a semi-static mirror, not an open proxy
to the Pinata API. Sign minting and metadata edits require a signed-in user.
Private assets are the dashboard owner's own index and store, tested against
a real `SqliteIndex` and a temp-dir store: only the owner reaches them.
"""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, index_api
from app.assets import router
from stargazer.utils.cid import compute_cid
from stargazer.utils.index import SqliteIndex
from stargazer.utils.pinata import _check_keyvalue_count, _check_keyvalue_lengths

JWT = "test-pinata-jwt"

CANNED_RECORDS = [
    {
        "cid": "bafybam",
        "name": "x.bam",
        "keyvalues": {"asset": "alignment", "_owner": "octocat"},
        "network": "public",
    },
    {
        "cid": "bafyr1",
        "name": "r1.fq",
        "keyvalues": {"asset": "r1"},
        "network": "public",
    },
]


class FakePinata:
    """Captures calls; returns canned values."""

    def __init__(self):
        self.query_calls = []
        self.sign_calls = []
        self.update_calls = []

    async def query(self, keyvalues):
        self.query_calls.append({"keyvalues": dict(keyvalues)})
        return list(CANNED_RECORDS)

    async def create_signed_upload_url(self, filename, keyvalues, max_file_size=None):
        _check_keyvalue_count(keyvalues)
        _check_keyvalue_lengths(keyvalues)
        self.sign_calls.append(
            {
                "filename": filename,
                "keyvalues": dict(keyvalues),
                "max_file_size": max_file_size,
            }
        )
        return "https://uploads.example/signed"

    async def update_metadata(self, cid, keyvalues):
        _check_keyvalue_lengths(keyvalues)
        self.update_calls.append({"cid": cid, "keyvalues": dict(keyvalues)})
        return {
            "cid": cid,
            "name": "x",
            "keyvalues": dict(keyvalues),
            "network": "public",
        }


@pytest.fixture
def fake_pinata(monkeypatch):
    """Swap the route-level Pinata client, reset the public cache, set env."""
    import app.assets as assets_mod

    fake = FakePinata()
    monkeypatch.setattr(assets_mod, "_pinata_client", fake)
    monkeypatch.setattr(assets_mod, "_public_cache", None)
    monkeypatch.setenv("PINATA_JWT", JWT)
    return fake


@pytest.fixture
def client():
    """A client for the asset routes alone."""
    bare = FastAPI()
    bare.include_router(router)
    return TestClient(bare, follow_redirects=False)


def _auth(client: TestClient, subject: str = "octocat") -> None:
    """Sign the client in as `subject`, the way Union forwards identity."""
    client.headers["X-User-Subject"] = subject
    client.headers["X-User-Claim-Name"] = '"Octo Cat"'


class TestAuth:
    """Anonymous: browsing OK; sign requires a session."""

    def test_anonymous_can_read_schema(self, fake_pinata, client):
        assert client.get("/assets/schema").status_code == 200

    def test_anonymous_can_list_public(self, fake_pinata, client):
        resp = client.get("/assets/list", params={"network": "public"})
        assert resp.status_code == 200

    def test_anonymous_can_download_public(self, fake_pinata, client, monkeypatch):
        monkeypatch.setenv("PINATA_GATEWAY", "https://gw.example")
        resp = client.get("/assets/download/bafy123", params={"network": "public"})
        assert resp.status_code == 302

    def test_anonymous_list_defaults_to_public(self, fake_pinata, client):
        resp = client.get("/assets/list")
        assert resp.status_code == 200
        assert resp.json() == CANNED_RECORDS
        assert len(fake_pinata.query_calls) == 1

    def test_anonymous_sign_401(self, fake_pinata, client):
        resp = client.post(
            "/assets/sign",
            json={"filename": "x", "keyvalues": {"asset": "alignment"}},
        )
        assert resp.status_code == 401


class TestSchema:
    def test_schema_lists_registered_assets_with_fields(self, fake_pinata, client):
        resp = client.get("/assets/schema")
        assert resp.status_code == 200
        schema = resp.json()
        fields = {f["name"]: f for f in schema["alignment"]}
        assert fields["sample_id"]["type"] == "str"
        assert fields["duplicates_marked"]["type"] == "bool"
        # Base plumbing fields never reach the form.
        assert "cid" not in fields
        assert "path" not in fields
        assert "keyvalues" not in fields


OWNER = "octocat"
READS = b"@r1\nACGT\n+\nIIII\n"


@pytest.fixture
def private_store(tmp_path, monkeypatch):
    """The dashboard's own index and store, in a temp dir, owned by OWNER."""
    index = SqliteIndex(tmp_path / "index.db")
    monkeypatch.setattr(index_api, "_index", index)
    monkeypatch.setenv("STARGAZER_STORE_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv("STARGAZER_OWNER", OWNER)
    monkeypatch.setattr(config, "OWNER_SUBJECT", OWNER)
    return tmp_path


def _upload(client, data=READS, filename="r1.fq", keyvalues=None):
    """Upload `data` as a private asset through the route."""
    keyvalues = keyvalues or {"asset": "r1", "sample_id": "S1"}
    return client.post(
        "/assets/upload",
        params={"filename": filename, "keyvalues": json.dumps(keyvalues)},
        content=data,
    )


def _expected_cid(tmp_path: Path, data: bytes) -> str:
    """The CID of `data`, worked out the same way the store does."""
    path = tmp_path / "expected"
    path.write_bytes(data)
    return compute_cid(path)


class TestPrivate:
    """The Private tab's routes on the owner's index and store."""

    def test_upload_then_list(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        resp = _upload(client)
        assert resp.status_code == 200
        cid = _expected_cid(private_store, READS)
        assert resp.json()["cid"] == cid

        listed = client.get("/assets/list", params={"network": "private"}).json()
        # A typed asset stores its declared fields, empty ones included.
        assert [(r["cid"], r["name"], r["keyvalues"]) for r in listed] == [
            (
                cid,
                "r1.fq",
                {
                    "asset": "r1",
                    "sample_id": "S1",
                    "mate_cid": "",
                    "sequencing_platform": "",
                    "_owner": OWNER,
                },
            )
        ]
        stored = private_store / "store" / "users" / OWNER / "assets" / cid / "r1.fq"
        assert stored.read_bytes() == READS
        assert fake_pinata.sign_calls == []

    def test_list_filters_by_keyvalue(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        _upload(client)
        _upload(client, b"other", "r2.fq", {"asset": "r2", "sample_id": "S1"})
        listed = client.get(
            "/assets/list", params={"network": "private", "asset": "r2"}
        ).json()
        assert [r["name"] for r in listed] == ["r2.fq"]

    def test_download_returns_the_bytes(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        cid = _upload(client).json()["cid"]
        resp = client.get(f"/assets/download/{cid}", params={"network": "private"})
        assert resp.status_code == 200
        assert resp.content == READS
        assert resp.headers["content-disposition"] == 'attachment; filename="r1.fq"'

    def test_download_unknown_cid_404(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        resp = client.get("/assets/download/bafynope", params={"network": "private"})
        assert resp.status_code == 404

    def test_update_merges_and_restamps_owner(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        cid = _upload(client).json()["cid"]
        resp = client.post(
            "/assets/update",
            json={
                "cid": cid,
                "network": "private",
                "keyvalues": {"asset": "r1", "sample_id": "S2"},
            },
        )
        assert resp.status_code == 200
        listed = client.get("/assets/list", params={"network": "private"}).json()
        assert listed[0]["keyvalues"] == {
            "asset": "r1",
            "sample_id": "S2",
            "mate_cid": "",
            "sequencing_platform": "",
            "_owner": OWNER,
        }
        assert fake_pinata.update_calls == []

    def test_bad_keyvalues_400_before_reading(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        resp = _upload(client, keyvalues={"sample_id": "S1"})
        assert resp.status_code == 400
        assert "asset" in resp.json()["detail"]
        assert client.get("/assets/list", params={"network": "private"}).json() == []

    def test_upload_over_the_cap_413(
        self, fake_pinata, private_store, client, monkeypatch
    ):
        import app.assets as assets_mod

        monkeypatch.setattr(assets_mod, "MAX_UPLOAD_BYTES", 10)
        _auth(client, OWNER)
        resp = _upload(client, b"x" * 11)
        assert resp.status_code == 413
        assert resp.json()["detail"] == "Uploads are capped at 10 bytes."
        assert client.get("/assets/list", params={"network": "private"}).json() == []

    def test_someone_else_gets_403(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        cid = _upload(client).json()["cid"]
        _auth(client, "mallory")
        assert _upload(client, b"theirs").status_code == 403
        assert (
            client.get("/assets/list", params={"network": "private"}).status_code == 403
        )
        assert (
            client.get(
                f"/assets/download/{cid}", params={"network": "private"}
            ).status_code
            == 403
        )
        resp = client.post(
            "/assets/update",
            json={"cid": cid, "network": "private", "keyvalues": {"asset": "r1"}},
        )
        assert resp.status_code == 403

    def test_anonymous_gets_401(self, fake_pinata, private_store, client):
        assert _upload(client).status_code == 401
        assert (
            client.get("/assets/list", params={"network": "private"}).status_code == 401
        )
        assert (
            client.get(
                "/assets/download/bafy1", params={"network": "private"}
            ).status_code
            == 401
        )

    def test_private_works_without_a_pinata_key(
        self, fake_pinata, private_store, client, monkeypatch
    ):
        monkeypatch.delenv("PINATA_JWT", raising=False)
        _auth(client, OWNER)
        assert _upload(client).status_code == 200
        assert (
            len(client.get("/assets/list", params={"network": "private"}).json()) == 1
        )
        assert (
            client.get("/assets/list", params={"network": "public"}).status_code == 503
        )


class TestPublicList:
    def test_serves_full_listing_from_cache(self, fake_pinata, client):
        """One unfiltered Pinata query feeds repeated public list calls."""
        first = client.get("/assets/list", params={"network": "public"})
        second = client.get("/assets/list", params={"network": "public"})
        assert first.json() == CANNED_RECORDS
        assert second.json() == CANNED_RECORDS
        assert len(fake_pinata.query_calls) == 1
        assert fake_pinata.query_calls[0]["keyvalues"] == {}

    def test_filters_apply_in_memory(self, fake_pinata, client):
        resp = client.get("/assets/list", params={"network": "public", "asset": "r1"})
        assert [r["cid"] for r in resp.json()] == ["bafyr1"]
        # Filtering happened app-side, not via Pinata params.
        assert fake_pinata.query_calls[0]["keyvalues"] == {}


class TestSign:
    def test_registered_key_returns_url_and_stamped_keyvalues(
        self, fake_pinata, client
    ):
        _auth(client)
        resp = client.post(
            "/assets/sign",
            json={
                "filename": "r1.fq",
                "keyvalues": {"asset": "r1", "sample_id": "S1"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["url"] == "https://uploads.example/signed"
        assert body["keyvalues"]["_owner"] == "octocat"
        assert body["keyvalues"]["asset"] == "r1"
        call = fake_pinata.sign_calls[0]
        assert call["filename"] == "r1.fq"
        assert call["keyvalues"]["_owner"] == "octocat"
        assert call["max_file_size"] is not None

    def test_unregistered_key_signs_verbatim(self, fake_pinata, client):
        _auth(client)
        resp = client.post(
            "/assets/sign",
            json={
                "filename": "sheet.tsv",
                "keyvalues": {"asset": "never_registered_key", "lanes": "4"},
                "network": "public",
            },
        )
        assert resp.status_code == 200
        call = fake_pinata.sign_calls[0]
        assert call["keyvalues"]["lanes"] == "4"
        assert call["keyvalues"]["_owner"] == "octocat"

    def test_registered_key_signs_extra_field(self, fake_pinata, client):
        _auth(client)
        resp = client.post(
            "/assets/sign",
            json={
                "filename": "r1.fq",
                "keyvalues": {"asset": "r1", "flowcell": "X"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["keyvalues"]["flowcell"] == "X"
        assert fake_pinata.sign_calls[0]["keyvalues"]["flowcell"] == "X"

    def test_too_many_fields_is_400(self, fake_pinata, client):
        """Nine keys fit; the stamped owner makes this R1's tenth."""
        _auth(client)
        extras = {f"x{i}": "v" for i in range(5)}
        resp = client.post(
            "/assets/sign",
            json={"filename": "r1.fq", "keyvalues": {"asset": "r1", **extras}},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == (
            "An upload can carry at most 9 metadata fields, counting the "
            "asset type and owner; this one has 10."
        )
        assert fake_pinata.sign_calls == []

    def test_validation_errors_are_400(self, fake_pinata, client):
        _auth(client)
        no_asset = client.post(
            "/assets/sign", json={"filename": "x", "keyvalues": {"a": "1"}}
        )
        assert no_asset.status_code == 400
        assert "asset" in no_asset.json()["detail"]

        reserved = client.post(
            "/assets/sign",
            json={
                "filename": "x.bam",
                "keyvalues": {"asset": "alignment", "_owner": "me"},
            },
        )
        assert reserved.status_code == 400
        assert fake_pinata.sign_calls == []

    def test_missing_filename_400(self, fake_pinata, client):
        _auth(client)
        resp = client.post("/assets/sign", json={"keyvalues": {"asset": "alignment"}})
        assert resp.status_code == 400


class TestUpdate:
    """`POST /assets/update` — owner-only metadata merge (plan 21 follow-up)."""

    def _post(self, client, **body):
        return client.post("/assets/update", json=body)

    def test_owner_can_update(self, fake_pinata, client):
        _auth(client, "octocat")  # owns CANNED bafybam
        resp = self._post(
            client,
            cid="bafybam",
            network="public",
            keyvalues={"asset": "alignment", "sample_id": "S2"},
        )
        assert resp.status_code == 200
        call = fake_pinata.update_calls[0]
        assert call["cid"] == "bafybam"
        # _owner re-stamped from the session, after validation.
        assert call["keyvalues"]["_owner"] == "octocat"
        assert call["keyvalues"]["sample_id"] == "S2"

    def test_overlong_value_is_400(self, fake_pinata, client):
        _auth(client, "octocat")
        resp = self._post(
            client,
            cid="bafybam",
            network="public",
            keyvalues={"asset": "alignment", "sample_id": "S" * 251},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == (
            "A metadata field's name and value can each be at most 250 "
            "characters; 'sample_id' has 251."
        )
        assert fake_pinata.update_calls == []

    def test_non_owner_403(self, fake_pinata, client):
        _auth(client, "mallory")  # bafybam is owned by octocat
        resp = self._post(
            client, cid="bafybam", network="public", keyvalues={"asset": "alignment"}
        )
        assert resp.status_code == 403
        assert fake_pinata.update_calls == []

    def test_unowned_record_403(self, fake_pinata, client):
        """Fail closed: an unowned record (CANNED bafyr1) edits for nobody."""
        _auth(client, "octocat")
        resp = self._post(
            client, cid="bafyr1", network="public", keyvalues={"asset": "r1"}
        )
        assert resp.status_code == 403
        assert fake_pinata.update_calls == []

    def test_unknown_cid_403(self, fake_pinata, client):
        _auth(client, "octocat")
        resp = self._post(
            client, cid="nope", network="public", keyvalues={"asset": "alignment"}
        )
        assert resp.status_code == 403

    def test_anonymous_401(self, fake_pinata, client):
        resp = self._post(
            client, cid="bafybam", network="public", keyvalues={"asset": "alignment"}
        )
        assert resp.status_code == 401

    def test_validation_400(self, fake_pinata, client):
        _auth(client, "octocat")
        # Owns the record, but the patch is invalid → 400 (ownership checked first).
        missing = self._post(
            client, cid="bafybam", network="public", keyvalues={"x": "1"}
        )
        assert missing.status_code == 400
        reserved = self._post(
            client,
            cid="bafybam",
            network="public",
            keyvalues={"asset": "alignment", "_owner": "me"},
        )
        assert reserved.status_code == 400
        assert fake_pinata.update_calls == []

    def test_missing_cid_400(self, fake_pinata, client):
        _auth(client, "octocat")
        assert self._post(client, keyvalues={"asset": "alignment"}).status_code == 400

    def test_not_configured_503(self, fake_pinata, client, monkeypatch):
        monkeypatch.delenv("PINATA_JWT", raising=False)
        _auth(client, "octocat")
        resp = self._post(
            client, cid="bafybam", network="public", keyvalues={"asset": "alignment"}
        )
        assert resp.status_code == 503


class TestDownload:
    def test_public_authed_redirects_to_dedicated_gateway(
        self, fake_pinata, client, monkeypatch
    ):
        monkeypatch.setenv("PINATA_GATEWAY", "https://gw.example")
        _auth(client)
        resp = client.get("/assets/download/bafy123", params={"network": "public"})
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://gw.example/ipfs/bafy123"

    def test_public_anonymous_redirects_to_the_same_gateway(
        self, fake_pinata, client, monkeypatch
    ):
        """Anonymous downloads use PINATA_GATEWAY too: public gateways rate-limit."""
        monkeypatch.setenv("PINATA_GATEWAY", "https://gw.example")
        resp = client.get("/assets/download/bafy123", params={"network": "public"})
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://gw.example/ipfs/bafy123"


class TestNotConfigured:
    def test_routes_503_without_jwt(self, fake_pinata, client, monkeypatch):
        monkeypatch.delenv("PINATA_JWT", raising=False)
        _auth(client)
        assert client.get("/assets/list").status_code == 503
        assert (
            client.get("/assets/list", params={"network": "public"}).status_code == 503
        )
        resp = client.post(
            "/assets/sign",
            json={"filename": "x.bam", "keyvalues": {"asset": "alignment"}},
        )
        assert resp.status_code == 503
