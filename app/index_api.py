"""
### Index API — the user's asset index, served by their dashboard.

On Union each user's dashboard owns their asset index: a SQLite file on the
dashboard pod (`STARGAZER_INDEX_URL`, a local path there), kept durable in the
bucket by Litestream. This router exposes it to the user's task and notebook
pods, which reach the dashboard at its in-cluster address and call it through
`stargazer.utils.index.HttpIndex`.

The routes run `SqliteIndex`'s operations and nothing else:

| Route | Does |
|---|---|
| `POST /index/assets` | Upsert a row |
| `POST /index/query` | Rows matching every filter |
| `GET /index/assets/{cid}` | One row, or 404 |
| `PATCH /index/assets/{cid}` | Merge keyvalues onto a row, or 404 |
| `DELETE /index/assets/{cid}` | Remove a row (idempotent) |

Rows are checked for shape only. Asset-schema validation (`build_asset()`)
happens where assets are created; rows here carry the reserved `_owner` key
and bundle metadata that `build_asset()` rightly rejects from users.

The in-cluster address skips Union's login, so these routes read no identity
headers. That gap is tracked on the ROADMAP ("App internal addresses skip
Union's login").

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from stargazer.utils.index import SqliteIndex
from stargazer.utils.storage import make_index

router = APIRouter()

# The dashboard's index, opened on first use; tests swap in their own.
_index: SqliteIndex | None = None


class Record(BaseModel):
    """One index row as a storage client writes it."""

    cid: str
    uri: str
    name: str
    keyvalues: dict[str, str]


class Query(BaseModel):
    """Keyvalue filters; a list value matches any of its entries."""

    filters: dict[str, str | list[str]] = {}


class Patch(BaseModel):
    """Keyvalues to merge onto a row."""

    keyvalues: dict[str, str]


def _get_index() -> SqliteIndex:
    """The dashboard's own SQLite index (`STARGAZER_INDEX_URL`, a local path)."""
    global _index
    if _index is None:
        index = make_index(os.environ["STARGAZER_INDEX_URL"])
        if not isinstance(index, SqliteIndex):
            raise HTTPException(
                status_code=500,
                detail="the dashboard's STARGAZER_INDEX_URL must be a local file",
            )
        _index = index
    return _index


@router.post("/index/assets")
async def upsert(record: Record) -> dict:
    """Insert or replace a row; returns the stored row."""
    return await _get_index().upsert(record.model_dump())


@router.post("/index/query")
async def query(body: Query) -> list[dict]:
    """Rows matching every filter, newest first."""
    return await _get_index().query(body.filters)


@router.get("/index/assets/{cid}")
async def get(cid: str) -> dict:
    """One row by CID."""
    row = await _get_index().get(cid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no row for {cid}")
    return row


@router.patch("/index/assets/{cid}")
async def merge(cid: str, patch: Patch) -> dict:
    """Merge keyvalues onto a row; returns the stored row."""
    try:
        return await _get_index().merge(cid, patch.keyvalues)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/index/assets/{cid}", status_code=204)
async def delete(cid: str) -> Response:
    """Remove a row; a missing row is already gone."""
    await _get_index().delete(cid)
    return Response(status_code=204)
