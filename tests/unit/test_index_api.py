"""Tests for the dashboard's index API and the HTTP client pods use to reach it."""

import httpx
import pytest
from fastapi import FastAPI

import stargazer.utils.storage as storage_mod
from app import index_api
from stargazer.assets.asset import assemble
from stargazer.assets.reads import R1, R2
from stargazer.utils.index import HttpIndex, SqliteIndex
from stargazer.utils.storage import StorageClient


def _record(cid: str, **keyvalues: str) -> dict:
    """A row as the storage client writes it."""
    return {
        "cid": cid,
        "uri": f"s3://b/users/u/assets/{cid}/{cid}.bin",
        "name": f"{cid}.bin",
        "keyvalues": keyvalues,
    }


@pytest.fixture
def served(tmp_path, monkeypatch):
    """The index router on a FastAPI app, backed by a real SQLite index."""
    sqlite = SqliteIndex(tmp_path / "dashboard_index.db")
    monkeypatch.setattr(index_api, "_index", sqlite)
    app = FastAPI()
    app.include_router(index_api.router)
    return app, sqlite


def _flaky(app, failures: int):
    """Wrap an ASGI app so its first `failures` HTTP requests answer 503."""
    state = {"left": failures, "calls": 0}

    async def wrapped(scope, receive, send):
        if scope["type"] == "http":
            state["calls"] += 1
            if state["left"] > 0:
                state["left"] -= 1
                await send(
                    {"type": "http.response.start", "status": 503, "headers": []}
                )
                await send({"type": "http.response.body", "body": b""})
                return
        await app(scope, receive, send)

    return wrapped, state


def _client(app, **kwargs) -> HttpIndex:
    """An HttpIndex talking to `app` in-process, with no backoff delay."""
    return HttpIndex(
        "http://dashboard.u-x-development.svc.cluster.local",
        transport=httpx.ASGITransport(app=app),
        backoff=0,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_rows_round_trip_through_the_dashboard(served):
    """An upsert over HTTP lands in the dashboard's index and queries back."""
    app, sqlite = served
    index = _client(app)

    row = await index.upsert(_record("bafyA", asset="r1", sample_id="S1"))
    [found] = await index.query({"asset": "r1", "sample_id": "S1"})

    assert row["cid"] == found["cid"] == "bafyA"
    assert found["keyvalues"] == {"asset": "r1", "sample_id": "S1"}
    assert (await sqlite.get("bafyA"))["name"] == "bafyA.bin"


@pytest.mark.asyncio
async def test_list_filters_cross_the_wire(served):
    """A list value still matches any of its entries."""
    app, _ = served
    index = _client(app)
    for cid, sample in (("bafyA", "S1"), ("bafyB", "S2"), ("bafyC", "S3")):
        await index.upsert(_record(cid, asset="r1", sample_id=sample))

    rows = await index.query({"sample_id": ["S1", "S3"]})

    assert sorted(r["cid"] for r in rows) == ["bafyA", "bafyC"]


@pytest.mark.asyncio
async def test_missing_rows(served):
    """Get of a missing CID is None; merging onto one raises; delete is idempotent."""
    app, _ = served
    index = _client(app)
    await index.upsert(_record("bafyA", asset="r1"))

    assert await index.get("bafyNope") is None
    with pytest.raises(ValueError, match="bafyNope"):
        await index.merge("bafyNope", {"tool": "bwa"})
    await index.delete("bafyA")
    await index.delete("bafyA")
    assert await index.get("bafyA") is None


@pytest.mark.asyncio
async def test_merge_keeps_other_keys(served):
    """A merge over HTTP adds keys and keeps the rest."""
    app, _ = served
    index = _client(app)
    await index.upsert(_record("bafyA", asset="r1", sample_id="S1"))

    row = await index.merge("bafyA", {"tool": "bwa"})

    assert row["keyvalues"] == {"asset": "r1", "sample_id": "S1", "tool": "bwa"}


@pytest.mark.asyncio
async def test_retries_a_dashboard_that_isnt_ready(served):
    """Two 503s, then success: the write lands on the third attempt."""
    app, _ = served
    flaky, state = _flaky(app, failures=2)

    await _client(flaky).upsert(_record("bafyA", asset="r1"))

    assert state["calls"] == 3
    assert (await _client(app).get("bafyA"))["cid"] == "bafyA"


@pytest.mark.asyncio
async def test_fails_loudly_when_retries_run_out(served):
    """A write that never lands raises instead of returning quietly."""
    app, _ = served
    flaky, state = _flaky(app, failures=10)

    with pytest.raises(httpx.HTTPStatusError):
        await _client(flaky, attempts=3).upsert(_record("bafyA", asset="r1"))

    assert state["calls"] == 3


@pytest.mark.asyncio
async def test_storage_client_through_the_dashboard(served, tmp_path, monkeypatch):
    """Uploads and assemble() work end to end with the index behind HTTP."""
    app, sqlite = served
    client = StorageClient(
        local_dir=tmp_path / "pod_local",
        store_root=str(tmp_path / "bucket"),
        index=_client(app),
    )
    monkeypatch.setattr(storage_mod, "default_client", client)
    for cls, name in ((R1, "s1_R1.fq"), (R2, "s1_R2.fq")):
        path = tmp_path / "work" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"reads in {name}\n")
        await cls().update(path, sample_id="S1")

    found = await assemble(sample_id="S1", asset=["r1", "r2"])

    assert sorted(type(a).__name__ for a in found) == ["R1", "R2"]
    assert len(await sqlite.query({"sample_id": "S1"})) == 2
