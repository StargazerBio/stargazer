"""Tests for public notebooks: Publish, Unpublish, their listing and their copy.

The dashboard belongs to ALICE, and her workspace runs through the real
`app.workspace_store` against a temp directory. Pinata's public network is
`FakePublic`, swapped in for the dashboard's Pinata client. It behaves the
way Pinata does where it matters here: a TUS upload runs the real client's
checks on its keyvalues before anything is sent, the same bytes are stored
once (the first upload's keyvalues stay, measured 2026-10-26), and a query
filters by keyvalues and leaves out unowned files.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

import app.assets as assets_mod
import app.public_notebooks as public_mod
from app import config
from app import workspace_store as ws
from app.admin_app import asgi_app
from stargazer.utils.cid import CidBuilder
from stargazer.utils.index import SqliteIndex
from stargazer.utils.pinata import _check_new_file

ALICE = "387300641116005877"
BOB = "111111111111111111"

pytestmark = pytest.mark.usefixtures("workspace_root")


def _notebook(name: str, description: str) -> str:
    """A workspace notebook's source with `name` and `description` declared."""
    return (
        "import marimo\n\n"
        "app = marimo.App()\n\n"
        "with app.setup:\n"
        f'    main_name = "{name}"\n'
        f'    main_description = "{description}"\n'
    )


QC = _notebook("QC run", "Quality control.")
BOBS = _notebook("Bob's pipeline", "Bob's take.")


def _cid(data: bytes) -> str:
    """The CID Pinata gives `data`."""
    builder = CidBuilder()
    builder.update(data)
    return builder.cid()


class FakePublic:
    """Pinata's public network, in memory."""

    def __init__(self):
        self.files: dict[str, dict] = {}
        self.data: dict[str, bytes] = {}
        self.uploads: dict[str, dict] = {}
        self.deleted: list[str] = []

    def add(self, source: str, **keyvalues: str) -> str:
        """Put `source` on the network with `keyvalues`; return its CID."""
        data = source.encode()
        cid = _cid(data)
        self.files[cid] = {
            "cid": cid,
            "name": f"{keyvalues.get('slug', 'x')}.py",
            "keyvalues": dict(keyvalues),
            "network": "public",
        }
        self.data[cid] = data
        return cid

    async def tus_create(self, filename, keyvalues, length):
        _check_new_file(keyvalues)
        url = f"https://uploads.example/{len(self.uploads)}"
        self.uploads[url] = {
            "filename": filename,
            "keyvalues": dict(keyvalues),
            "length": length,
            "bytes": b"",
        }
        return url

    async def tus_patch(self, location, offset, chunk):
        upload = self.uploads[location]
        assert offset == len(upload["bytes"])
        upload["bytes"] += chunk
        if len(upload["bytes"]) < upload["length"]:
            return None
        cid = _cid(upload["bytes"])
        if cid not in self.files:
            self.files[cid] = {
                "cid": cid,
                "name": upload["filename"],
                "keyvalues": upload["keyvalues"],
                "network": "public",
            }
            self.data[cid] = upload["bytes"]
        return cid

    async def query(self, keyvalues):
        return [
            dict(f)
            for f in self.files.values()
            if f["keyvalues"].get("_owner")
            and all(f["keyvalues"].get(k) == v for k, v in keyvalues.items())
        ]

    async def get(self, cid):
        f = self.files.get(cid)
        return dict(f) if f and f["keyvalues"].get("_owner") else None

    async def delete(self, component):
        self.deleted.append(component.cid)
        self.files.pop(component.cid, None)

    async def read(self, cid):
        """The gateway: the bytes stored under `cid`, as text."""
        return self.data[cid].decode()

    def notebooks(self) -> list[dict]:
        """The stored notebook records."""
        return [
            f for f in self.files.values() if f["keyvalues"].get("asset") == "notebook"
        ]


@pytest.fixture(autouse=True)
def _owned_by_alice(monkeypatch):
    """Every test's dashboard is ALICE's."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", ALICE)


@pytest.fixture
def public(monkeypatch):
    """The public tier, on: the org's key and `FakePublic` behind it."""
    fake = FakePublic()
    monkeypatch.setenv("PINATA_JWT", "test-jwt")
    monkeypatch.setattr(config, "PUBLIC_ASSETS", True)
    monkeypatch.setattr(assets_mod, "_pinata_client", fake)
    monkeypatch.setattr(assets_mod, "_public_cache", None)
    monkeypatch.setattr(public_mod, "_read_public", fake.read)
    return fake


@pytest.fixture
def client():
    """ALICE, signed in to her dashboard (no lifespan, so no Flyte init)."""
    c = TestClient(asgi_app, follow_redirects=False)
    c.headers["X-User-Subject"] = ALICE
    c.headers["X-User-Claim-Name"] = '"Alice Ng"'
    return c


def _put(filename: str, src: str) -> None:
    """Seed ALICE's workspace directly."""
    asyncio.run(ws.create_workspace_notebook(ALICE, filename, src))


def _get(filename: str) -> str | None:
    """Read ALICE's workspace directly."""
    return asyncio.run(ws.get_workspace_notebook(ALICE, filename))


def _publish(client, slug="qc-run"):
    return client.post("/workspace/publish", data={"slug": slug})


def _copy(client, cid):
    return client.post("/workspace/copy", data={"slug": cid, "section": "public"})


class TestPublish:
    def test_publish_puts_the_notebook_on_the_public_tier(self, public, client):
        _put("qc-run.py", QC)
        resp = _publish(client)
        assert resp.status_code == 200
        [record] = public.notebooks()
        assert resp.json() == {"slug": "qc-run", "cid": record["cid"]}
        assert record["name"] == "qc-run.py"
        assert record["keyvalues"] == {
            "asset": "notebook",
            "title": "QC run",
            "description": "Quality control.",
            "slug": "qc-run",
            "_owner": ALICE,
        }
        assert public.data[record["cid"]] == QC.encode()

    def test_publishing_again_replaces_the_earlier_record(self, public, client):
        _put("qc-run.py", QC)
        first = _publish(client).json()["cid"]
        edited = _notebook("QC run", "Quality control, v2.")
        asyncio.run(ws.update_workspace_notebook(ALICE, "qc-run.py", edited))
        second = _publish(client).json()["cid"]
        assert second != first
        assert [r["cid"] for r in public.notebooks()] == [second]
        assert public.deleted == [first]

    def test_another_users_notebook_with_the_same_slug_stays(self, public, client):
        bobs = public.add(BOBS, asset="notebook", slug="qc-run", _owner=BOB)
        _put("qc-run.py", QC)
        assert _publish(client).status_code == 200
        assert bobs in public.files
        assert public.deleted == []

    def test_bytes_already_public_under_another_record_are_refused(
        self, public, client
    ):
        theirs = public.add(QC, asset="notebook", slug="qc", _owner=BOB)
        mine = public.add(
            _notebook("QC run", "older"), asset="notebook", slug="qc-run", _owner=ALICE
        )
        _put("qc-run.py", QC)
        resp = _publish(client)
        assert resp.status_code == 409
        assert resp.json() == {"error": "An identical notebook is already public."}
        assert set(public.files) == {theirs, mine}
        assert public.deleted == []

    def test_an_overlong_description_is_refused_before_upload(self, public, client):
        _put("qc-run.py", _notebook("QC run", "d" * 251))
        resp = _publish(client)
        assert resp.status_code == 400
        assert resp.json() == {
            "error": "A metadata field's name and value can each be at most 250 "
            "characters; 'description' has 251."
        }
        assert public.uploads == {}

    def test_missing_notebook_is_404(self, public, client):
        assert _publish(client, "nope").status_code == 404
        assert public.uploads == {}


class TestUnpublish:
    def test_unpublish_removes_only_the_owners_record(self, public, client):
        mine = public.add(QC, asset="notebook", slug="qc-run", _owner=ALICE)
        bobs = public.add(BOBS, asset="notebook", slug="qc-run", _owner=BOB)
        resp = client.post("/workspace/unpublish", data={"slug": "qc-run"})
        assert resp.status_code == 200
        assert public.deleted == [mine]
        assert list(public.files) == [bobs]

    def test_unpublishing_what_isnt_published_is_404(self, public, client):
        public.add(BOBS, asset="notebook", slug="qc-run", _owner=BOB)
        resp = client.post("/workspace/unpublish", data={"slug": "qc-run"})
        assert resp.status_code == 404
        assert public.deleted == []


class TestDashboard:
    def test_workspace_tiles_offer_publish_and_unpublish(self, public, client):
        _put("qc-run.py", QC)
        _put("draft.py", _notebook("Draft", ""))
        public.add(QC, asset="notebook", slug="qc-run", _owner=ALICE)
        html = client.get("/").text
        assert 'data-unpublish-slug="qc-run"' in html
        assert 'data-unpublish-slug="draft"' not in html
        assert 'data-publish-slug="qc-run"' in html
        assert 'data-publish-slug="draft"' in html


class TestCopy:
    def test_copy_writes_the_public_notebook_to_the_workspace(self, public, client):
        bobs = public.add(
            BOBS,
            asset="notebook",
            title="Bob's pipeline",
            description="Bob's take.",
            slug="bobs-pipeline",
            _owner=BOB,
        )
        resp = _copy(client, bobs)
        assert resp.status_code == 200
        assert resp.json()["slug"] == "bob-s-pipeline"
        assert _get("bob-s-pipeline.py") == BOBS
        assert _copy(client, bobs).status_code == 409

    def test_copy_of_anything_but_a_public_notebook_is_404(self, public, client):
        other = public.add("x", asset="alignment", _owner=BOB)
        assert _copy(client, other).status_code == 404


class TestPublicAssetsOff:
    def test_routes_503_and_nothing_is_offered(self, public, client, monkeypatch):
        monkeypatch.setattr(config, "PUBLIC_ASSETS", False)
        _put("qc-run.py", QC)
        cid = public.add(BOBS, asset="notebook", slug="bobs", _owner=BOB)
        assert _publish(client).status_code == 503
        unpublish = client.post("/workspace/unpublish", data={"slug": "qc-run"})
        assert unpublish.status_code == 503
        assert _copy(client, cid).status_code == 503
        html = client.get("/").text
        assert 'data-source="public"' not in html
        assert 'data-publish-slug="qc-run"' not in html
        assert public.uploads == {}


class TestAssetBrowser:
    """Notebooks are entries in the asset browser, but uploads never make one."""

    def test_mine_lists_notebook_rows(self, public, client, tmp_path, monkeypatch):
        index = SqliteIndex(tmp_path / "index.db")
        monkeypatch.setattr(assets_mod, "_index", index)
        for cid, kind in (("bafynb", "notebook"), ("bafyr1", "r1")):
            record = {
                "cid": cid,
                "uri": f"/store/{cid}",
                "name": f"{cid}.x",
                "keyvalues": {"asset": kind, "_owner": ALICE},
            }
            asyncio.run(index.upsert(record))
        listed = client.get("/assets/list", params={"source": "mine"}).json()
        assert sorted(r["cid"] for r in listed) == ["bafynb", "bafyr1"]

    def test_public_lists_public_notebooks(self, public, client):
        qc = public.add(QC, asset="notebook", slug="qc-run", _owner=ALICE)
        r1 = public.add("reads", asset="r1", _owner=ALICE)
        listed = client.get(
            "/assets/list", params={"source": "public", "asset": "notebook"}
        ).json()
        assert [(r["cid"], r["source"]) for r in listed] == [(qc, "public")]
        everything = client.get("/assets/list", params={"source": "public"}).json()
        assert sorted(r["cid"] for r in everything) == sorted([qc, r1])

    def test_upload_form_doesnt_offer_notebooks(self, public, client):
        schema = client.get("/assets/schema").json()
        assert "notebook" not in schema
        assert "r1" in schema
