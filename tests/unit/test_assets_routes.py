"""Tests for the asset-manager API routes.

Route tests mount the router on a bare FastAPI app: the dashboard's owner
gate (tested in `test_app.py`) sits in front of these routes there, and is
not what's under test here. Identity comes from the `X-User-Subject`
header Union's auth layer sets on every request. The Pinata client is swapped for a fake via the
`app.assets._pinata_client` module attribute — query returns canned records,
and its TUS upload keeps the chunks it's sent and answers the last one with
their CID. Each call captures its args, and creating an upload runs the real
client's keyvalue checks, which happen before any request.

Auth model: public browsing (schema, list, download) is anonymous — public
bytes are world-readable on IPFS anyway, and the listing is served from an
in-process TTL cache so the admin is a semi-static mirror, not an open proxy
to the Pinata API. Public uploads and metadata edits require a signed-in user.
Private assets are the dashboard owner's own index and store, tested against
a real `SqliteIndex` and a temp-dir store: only the owner reaches them.
"""

import base64
import itertools
import json
import random
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.assets as assets_mod
from app import config, notebooks
from app.assets import router
from stargazer.utils.cid import CidBuilder, compute_cid
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

# The public listing's entries: the records, each stamped with its source.
PUBLIC_ENTRIES = [{**r, "source": "public"} for r in CANNED_RECORDS]


class FakePinata:
    """Captures calls; returns canned values."""

    def __init__(self):
        self.query_calls = []
        self.update_calls = []
        self.tus_created = []
        self.tus_patches = []
        self.deleted = []
        # The CID Pinata answers the last chunk with, when it isn't theirs.
        self.stored_cid = None

    async def query(self, keyvalues):
        self.query_calls.append({"keyvalues": dict(keyvalues)})
        return list(CANNED_RECORDS)

    async def tus_create(self, filename, keyvalues, length):
        _check_keyvalue_count(keyvalues)
        _check_keyvalue_lengths(keyvalues)
        self.tus_created.append(
            {"filename": filename, "keyvalues": dict(keyvalues), "length": length}
        )
        return "https://uploads.example/files/up1"

    async def tus_patch(self, location, offset, chunk):
        self.tus_patches.append((location, offset, chunk))
        received = b"".join(c for _, _, c in self.tus_patches)
        if len(received) < self.tus_created[-1]["length"]:
            return None
        builder = CidBuilder()
        builder.update(received)
        return self.stored_cid or builder.cid()

    async def delete(self, component):
        self.deleted.append(component.cid)

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
    """Anonymous: browsing OK; uploading requires a session."""

    def test_anonymous_public_list(self, fake_pinata, client):
        resp = client.get("/assets/list", params={"source": "public"})
        assert resp.status_code == 200
        assert resp.json() == PUBLIC_ENTRIES
        assert len(fake_pinata.query_calls) == 1

    def test_anonymous_public_upload_401(self, fake_pinata, client):
        assert _tus_create(client, network="public").status_code == 401
        assert fake_pinata.tus_created == []


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
    monkeypatch.setattr(assets_mod, "_index", index)
    monkeypatch.setenv("STARGAZER_STORE_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv("STARGAZER_OWNER", OWNER)
    monkeypatch.setattr(config, "OWNER_SUBJECT", OWNER)
    return tmp_path


def _upload(client, data=READS, filename="r1.fq", keyvalues=None):
    """Upload `data` as a private asset over TUS in one piece.

    Returns the creation's response if it was refused, else the piece's,
    whose `Stargazer-Cid` header is the stored CID.
    """
    created = _tus_create(client, len(data), filename=filename, keyvalues=keyvalues)
    if created.status_code != 201:
        return created
    return _tus_patch(client, created.headers["Location"], 0, data)


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
        assert resp.status_code == 204
        cid = _expected_cid(private_store, READS)
        assert resp.headers["Stargazer-Cid"] == cid

        listed = client.get("/assets/list", params={"source": "mine"}).json()
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
        (stored,) = [p for p in _uploads_dir(private_store).rglob("r1.fq")]
        assert stored.read_bytes() == READS
        assert fake_pinata.tus_created == []

    def test_list_filters_by_keyvalue(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        _upload(client)
        _upload(client, b"other", "r2.fq", {"asset": "r2", "sample_id": "S1"})
        listed = client.get(
            "/assets/list", params={"source": "mine", "asset": "r2"}
        ).json()
        assert [r["name"] for r in listed] == ["r2.fq"]

    def test_download_returns_the_bytes(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        cid = _upload(client).headers["Stargazer-Cid"]
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
        cid = _upload(client).headers["Stargazer-Cid"]
        resp = client.post(
            "/assets/update",
            json={
                "cid": cid,
                "network": "private",
                "keyvalues": {"asset": "r1", "sample_id": "S2"},
            },
        )
        assert resp.status_code == 200
        listed = client.get("/assets/list", params={"source": "mine"}).json()
        assert listed[0]["keyvalues"] == {
            "asset": "r1",
            "sample_id": "S2",
            "mate_cid": "",
            "sequencing_platform": "",
            "_owner": OWNER,
        }
        assert fake_pinata.update_calls == []

    def test_someone_else_gets_403(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        cid = _upload(client).headers["Stargazer-Cid"]
        _auth(client, "mallory")
        assert _upload(client, b"theirs").status_code == 403
        assert client.get("/assets/list", params={"source": "mine"}).status_code == 403
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
        assert client.get("/assets/list", params={"source": "mine"}).status_code == 401
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
        assert _upload(client).status_code == 204
        assert len(client.get("/assets/list", params={"source": "mine"}).json()) == 1
        assert (
            client.get("/assets/list", params={"source": "public"}).status_code == 503
        )


class TestPublicList:
    def test_serves_full_listing_from_cache(self, fake_pinata, client):
        """One unfiltered Pinata query feeds repeated public list calls."""
        first = client.get("/assets/list", params={"source": "public"})
        second = client.get("/assets/list", params={"source": "public"})
        assert first.json() == PUBLIC_ENTRIES
        assert second.json() == PUBLIC_ENTRIES
        assert len(fake_pinata.query_calls) == 1
        assert fake_pinata.query_calls[0]["keyvalues"] == {}

    def test_filters_apply_in_memory(self, fake_pinata, client):
        resp = client.get("/assets/list", params={"source": "public", "asset": "r1"})
        assert [r["cid"] for r in resp.json()] == ["bafyr1"]
        # Filtering happened app-side, not via Pinata params.
        assert fake_pinata.query_calls[0]["keyvalues"] == {}


def _list(client, *sources: str, **filters: str):
    """GET the listing for `sources`, filtered by keyvalue `filters`."""
    params = [("source", s) for s in sources] + list(filters.items())
    return client.get("/assets/list", params=params)


class TestSources:
    """One listing over the user's assets, the public tier and the built-in notebooks."""

    def test_stargazer_lists_every_builtin_notebook(self, client):
        entries = _list(client, "stargazer").json()
        assert {e["keyvalues"]["slug"] for e in entries} == {
            n.slug for n in notebooks.NOTEBOOKS
        }
        tasks = next(e for e in entries if e["keyvalues"]["slug"] == "tasks")
        assert tasks == {
            "cid": compute_cid(notebooks.NOTEBOOKS_PKG_DIR / "tutorials" / "tasks.py"),
            "name": "tasks.py",
            "source": "stargazer",
            "keyvalues": {
                "asset": "notebook",
                "category": "tutorial",
                "title": "2. Tasks",
                "description": "Define a single task with typed asset I/O.",
                "slug": "tasks",
            },
        }

    def test_filters_apply_to_builtin_notebooks(self, client):
        entries = _list(client, "stargazer", category="workflow").json()
        assert [e["keyvalues"]["slug"] for e in entries] == ["scrna-pipeline"]

    def test_mine_and_stargazer_together(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        cid = _upload(client).headers["Stargazer-Cid"]
        entries = _list(client, "mine", "stargazer").json()
        assert [(e["cid"], e["source"]) for e in entries if e["source"] == "mine"] == [
            (cid, "mine")
        ]
        assert len(entries) == len(notebooks.NOTEBOOKS) + 1
        assert {e["source"] for e in entries} == {"mine", "stargazer"}

    def test_builtin_notebooks_arent_mine(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        assert _list(client, "mine", asset="notebook").json() == []
        assert len(_list(client, "stargazer", asset="notebook").json()) == len(
            notebooks.NOTEBOOKS
        )

    def test_anonymous_mine_is_401(self, fake_pinata, private_store, client):
        assert _list(client, "mine").status_code == 401
        assert _list(client, "mine", "stargazer").status_code == 401

    def test_public_off_is_503(self, fake_pinata, client, monkeypatch):
        monkeypatch.setattr(config, "PUBLIC_ASSETS", False)
        assert _list(client, "public").status_code == 503
        assert _list(client, "stargazer", "public").status_code == 503
        assert _list(client, "stargazer").status_code == 200

    def test_a_failing_public_tier_leaves_the_other_sources(
        self, fake_pinata, private_store, client, monkeypatch
    ):
        async def down(_keyvalues):
            raise RuntimeError("upstream down")

        monkeypatch.setattr(fake_pinata, "query", down)
        _auth(client, OWNER)
        cid = _upload(client).headers["Stargazer-Cid"]
        resp = _list(client, "mine", "public", "stargazer")
        assert resp.status_code == 200
        assert resp.headers["Stargazer-Unavailable"] == "public"
        assert {e["source"] for e in resp.json()} == {"mine", "stargazer"}
        assert [e["cid"] for e in resp.json() if e["source"] == "mine"] == [cid]
        assert "Stargazer-Unavailable" not in _list(client, "stargazer").headers

    def test_no_or_unknown_source_is_400(self, client):
        assert _list(client).status_code == 400
        assert _list(client, "elsewhere").status_code == 400

    def test_builtin_notebook_downloads_its_source(self, client):
        path = notebooks.NOTEBOOKS_PKG_DIR / "tutorials" / "tasks.py"
        resp = client.get(
            f"/assets/download/{compute_cid(path)}", params={"network": "stargazer"}
        )
        assert resp.status_code == 200
        assert resp.content == path.read_bytes()
        assert resp.headers["content-disposition"] == 'attachment; filename="tasks.py"'
        missing = client.get(
            "/assets/download/bafynope", params={"network": "stargazer"}
        )
        assert missing.status_code == 404


class TestUpdate:
    """`POST /assets/update` — owner-only metadata merge."""

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
    @pytest.mark.parametrize("signed_in", [True, False])
    def test_public_redirects_to_the_dedicated_gateway(
        self, fake_pinata, client, monkeypatch, signed_in
    ):
        """Signed in or not, public downloads use PINATA_GATEWAY: public gateways rate-limit."""
        monkeypatch.setenv("PINATA_GATEWAY", "https://gw.example")
        if signed_in:
            _auth(client)
        resp = client.get("/assets/download/bafy123", params={"network": "public"})
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://gw.example/ipfs/bafy123"


class TestNotConfigured:
    def test_public_routes_503_when_public_assets_are_off(
        self, fake_pinata, private_store, client, monkeypatch
    ):
        monkeypatch.setattr(config, "PUBLIC_ASSETS", False)
        _auth(client, OWNER)
        assert (
            client.get("/assets/list", params={"source": "public"}).status_code == 503
        )
        assert _tus_create(client, network="public").status_code == 503
        assert fake_pinata.query_calls == fake_pinata.tus_created == []
        assert client.get("/assets/list", params={"source": "mine"}).status_code == 200

    def test_routes_503_without_jwt(self, fake_pinata, client, monkeypatch):
        monkeypatch.delenv("PINATA_JWT", raising=False)
        _auth(client)
        assert (
            client.get("/assets/list", params={"source": "public"}).status_code == 503
        )
        assert _tus_create(client, network="public").status_code == 503


BIG = random.Random(0).randbytes(700_000)
TUS = {"Tus-Resumable": "1.0.0"}


def _metadata(**pairs: str) -> str:
    """A TUS `Upload-Metadata` header: `key base64(value)` pairs."""
    return ",".join(
        f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in pairs.items()
    )


def _tus_create(
    client, length=None, filename="big.fq", keyvalues=None, network="private"
):
    """POST a new TUS upload to `network`; returns the response."""
    keyvalues = keyvalues or {"asset": "r1", "sample_id": "S1"}
    return client.post(
        "/assets/tus",
        headers={
            **TUS,
            "Upload-Length": str(len(BIG) if length is None else length),
            "Upload-Metadata": _metadata(
                filename=filename, network=network, keyvalues=json.dumps(keyvalues)
            ),
        },
    )


def _tus_patch(client, location, offset, data):
    """PATCH `data` onto an upload at `offset`."""
    return client.patch(
        location,
        headers={
            **TUS,
            "Upload-Offset": str(offset),
            "Content-Type": "application/offset+octet-stream",
        },
        content=data,
    )


def _tus_upload(client, data=BIG, cuts=(250_000, 500_000), **create):
    """Create an upload and send `data` in pieces split at `cuts`."""
    location = _tus_create(client, len(data), **create).headers["Location"]
    bounds = [0, *cuts, len(data)]
    for start, end in itertools.pairwise(bounds):
        resp = _tus_patch(client, location, start, data[start:end])
        assert resp.status_code == 204, resp.text
    return location, resp


def _uploads_dir(store: Path) -> Path:
    """Where in-progress uploads land in the owner's store."""
    return store / "store" / "users" / OWNER / "uploads"


class TestTus:
    """Resumable private uploads over TUS, into the owner's store and index."""

    def test_three_chunks_store_the_file_under_its_cid(
        self, fake_pinata, private_store, client
    ):
        _auth(client, OWNER)
        _, done = _tus_upload(client)
        cid = _expected_cid(private_store, BIG)
        assert done.headers["Upload-Offset"] == str(len(BIG))
        assert done.headers["Stargazer-Cid"] == cid
        listed = client.get("/assets/list", params={"source": "mine"}).json()
        assert [(r["cid"], r["name"]) for r in listed] == [(cid, "big.fq")]
        resp = client.get(f"/assets/download/{cid}", params={"network": "private"})
        assert resp.content == BIG

    def test_same_file_twice_keeps_one_copy(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        _tus_upload(client)
        _tus_upload(client)
        listed = client.get("/assets/list", params={"source": "mine"}).json()
        assert len(listed) == 1
        stored = [p for p in _uploads_dir(private_store).rglob("*") if p.is_file()]
        assert len(stored) == 1

    def test_head_reports_the_offset_to_resume_from(
        self, fake_pinata, private_store, client
    ):
        _auth(client, OWNER)
        location = _tus_create(client).headers["Location"]
        _tus_patch(client, location, 0, BIG[:300_000])
        head = client.head(location, headers=TUS)
        assert head.headers["Upload-Offset"] == "300000"
        assert head.headers["Upload-Length"] == str(len(BIG))
        done = _tus_patch(client, location, 300_000, BIG[300_000:])
        assert done.headers["Stargazer-Cid"] == _expected_cid(private_store, BIG)

    def test_patch_at_the_wrong_offset_is_a_conflict(
        self, fake_pinata, private_store, client
    ):
        _auth(client, OWNER)
        location = _tus_create(client).headers["Location"]
        _tus_patch(client, location, 0, BIG[:1000])
        assert _tus_patch(client, location, 0, BIG[:1000]).status_code == 409

    def test_over_the_cap_is_refused(self, fake_pinata, private_store, client):
        _auth(client, OWNER)
        length = assets_mod.TUS_MAX_BYTES + 1
        assert _tus_create(client, length=length).status_code == 413

    def test_bad_keyvalues_are_refused_before_any_bytes(
        self, fake_pinata, private_store, client
    ):
        _auth(client, OWNER)
        resp = _tus_create(client, keyvalues={"sample_id": "S1"})
        assert resp.status_code == 422
        assert not _uploads_dir(private_store).exists()

    def test_only_the_owner_uploads(self, fake_pinata, private_store, client):
        assert _tus_create(client).status_code == 401
        _auth(client, "someone-else")
        assert _tus_create(client).status_code == 403

    def test_an_idle_upload_is_dropped(
        self, fake_pinata, private_store, client, monkeypatch
    ):
        _auth(client, OWNER)
        location = _tus_create(client).headers["Location"]
        _tus_patch(client, location, 0, BIG[:1000])
        monkeypatch.setattr(assets_mod, "TUS_IDLE_SECONDS", 0)
        _tus_create(client)
        assert _tus_patch(client, location, 1000, BIG[1000:2000]).status_code == 404


class TestTusPublic:
    """Public uploads over TUS, each piece passed on to Pinata's TUS upload."""

    def test_three_chunks_are_passed_on_in_order(self, fake_pinata, client, tmp_path):
        _auth(client, "someone-signed-in")
        _, done = _tus_upload(client, network="public")
        cid = _expected_cid(tmp_path, BIG)
        assert done.headers["Stargazer-Cid"] == cid
        assert [(loc, off) for loc, off, _ in fake_pinata.tus_patches] == [
            ("https://uploads.example/files/up1", 0),
            ("https://uploads.example/files/up1", 250_000),
            ("https://uploads.example/files/up1", 500_000),
        ]
        assert b"".join(c for _, _, c in fake_pinata.tus_patches) == BIG
        (created,) = fake_pinata.tus_created
        assert (created["filename"], created["length"]) == ("big.fq", len(BIG))
        assert created["keyvalues"]["_owner"] == "someone-signed-in"
        assert created["keyvalues"]["sample_id"] == "S1"
        assert fake_pinata.deleted == []

    def test_a_cid_mismatch_removes_the_file(self, fake_pinata, client):
        _auth(client)
        fake_pinata.stored_cid = "bafywrong"
        location = _tus_create(client, network="public").headers["Location"]
        assert _tus_patch(client, location, 0, BIG[:300_000]).status_code == 204
        done = _tus_patch(client, location, 300_000, BIG[300_000:])
        assert done.status_code == 422
        assert "Stargazer-Cid" not in done.headers
        assert fake_pinata.deleted == ["bafywrong"]
        assert client.head(location, headers=TUS).status_code == 404

    def test_too_many_fields_are_refused_before_pinata(self, fake_pinata, client):
        """Nine keys fit; the stamped owner makes this R1's tenth."""
        _auth(client)
        extras = {f"x{i}": "v" for i in range(5)}
        resp = _tus_create(
            client, network="public", keyvalues={"asset": "r1", **extras}
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == (
            "An upload can carry at most 9 metadata fields, counting the "
            "asset type and owner; this one has 10."
        )
        assert fake_pinata.tus_created == []

    def test_only_its_uploader_sends_the_pieces(self, fake_pinata, client):
        _auth(client, "uploader")
        location = _tus_create(client, network="public").headers["Location"]
        _auth(client, "someone-else")
        assert client.head(location, headers=TUS).status_code == 403
        assert _tus_patch(client, location, 0, BIG[:1000]).status_code == 403
        assert fake_pinata.tus_patches == []

    def test_a_piece_bigger_than_a_chunk_is_refused(
        self, fake_pinata, client, monkeypatch
    ):
        _auth(client)
        monkeypatch.setattr(assets_mod, "TUS_CHUNK_BYTES", 1000)
        location = _tus_create(client, network="public").headers["Location"]
        assert _tus_patch(client, location, 0, BIG[:2000]).status_code == 413
        assert fake_pinata.tus_patches == []
