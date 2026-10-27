"""
### Asset browser API routes.

APIRouter included by the dashboard, serving the asset explorer on its home
page (`templates/_assets.html`). Its listing (`GET /assets/list`) is one list
over the sources the explorer asks for, each entry stamped with its `source`:

- **`mine`** is the dashboard owner's own asset index and store, the same
  ones their tasks write to; the routes that act on one record call it the
  `private` network. Downloads stream back out, and metadata edits merge
  onto the index row. Only the owner reaches them: another signed-in user
  gets a 403.
- **`public`** is Pinata's public network, through the org's shared key (a
  Flyte secret, `app.admin_app`), public notebooks included. Downloads
  redirect to the gateway, so those bytes never transit the dashboard.
  Pinata's private network is never used: with a shared key it would keep
  nothing private. Without a key (the devbox, which drops app secrets, or a
  local run with none), or with public assets turned off for the deploy
  (`config.PUBLIC_ASSETS`), the public listing, edits and uploads 503 and
  the explorer doesn't offer Public.
- **`stargazer`** is the notebooks shipped in the image
  (`app.notebooks.shipped_entries`), listed but never stored. Anyone may
  list them, and their source downloads from the `stargazer` network.

Auth model: on the hosted deploy a request's identity is its signed Union
token (`app.identity`). The routes still degrade for an anonymous request (a
local run): public browsing works, while private routes, uploads and edits
401. The public listing is served from an in-process TTL cache so the
dashboard acts as a semi-static read-only mirror rather than an open proxy
to the Pinata API. Public edits fail closed: only a record's `_owner` may
change it.

Uploads to either network come in resumable pieces over the TUS protocol
(`/assets/tus`), up to 10 GB, while the file's CID is worked out as they
pass (`CidBuilder`), so it never touches the dashboard's disk.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import base64
import binascii
import dataclasses
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, get_type_hints

import flyte.storage
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from app import config, notebooks
from app.identity import User, user_from_request
from stargazer.assets import ASSET_REGISTRY, Notebook, build_asset
from stargazer.assets.asset import Asset
from stargazer.utils.cid import CidBuilder
from stargazer.utils.index import SqlIndex, make_index
from stargazer.utils.pinata import TUS_CHUNK_BYTES, PinataClient, _stamp_owner
from stargazer.utils.storage import StorageClient

router = APIRouter()

# Uploads over TUS. The browser sends `TUS_CHUNK_BYTES` pieces: small enough
# for one request through Cloudflare and for the dashboard's memory. Pinata's
# TUS takes files up to 10 GiB.
TUS_VERSION = "1.0.0"
TUS_MAX_BYTES = 10 * 1024**3
# An upload no request has touched for this long is dropped. Its multipart
# upload is left unfinished, so nothing appears at its path; the bucket's
# lifecycle has to clear the parts, since the pods' role can't abort one.
TUS_IDLE_SECONDS = 3600.0

# The anonymous public tab reads this cache, refreshed lazily — stale
# entries cost at most one Pinata listing per TTL regardless of traffic.
PUBLIC_CACHE_TTL = 60.0

# Module attributes resolved at call time so tests can swap in fakes.
_index: SqlIndex | None = None
_pinata_client: PinataClient | None = None
_public_cache: tuple[float, list[dict]] | None = None
# Single-flight guard for cache refreshes: concurrent anonymous requests on a
# cold/expired cache would otherwise each fan out their own Pinata listing.
_public_cache_lock = asyncio.Lock()


def _get_index() -> SqlIndex:
    """The owner's asset index (`STARGAZER_INDEX_URL`), opened on first use.

    The same index their tasks and notebooks write to: their DSQL table on
    Union, the devbox's Postgres server, a SQLite file locally.
    """
    global _index
    if _index is None:
        _index = make_index(os.environ["STARGAZER_INDEX_URL"])
    return _index


def _pinata() -> PinataClient:
    """The shared Pinata client, created lazily."""
    global _pinata_client
    if _pinata_client is None:
        _pinata_client = PinataClient()
    return _pinata_client


def _require_user(request: Request) -> User:
    """The signed-in user, or a 401. Ownership of a record is checked per route."""
    user = user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="not signed in")
    return user


def _require_owner(request: Request) -> User:
    """The signed-in user if they own this dashboard, else a 401 or 403."""
    return _check_owner(_require_user(request))


def _check_owner(user: User) -> User:
    """`user` if they own this dashboard, else a 403.

    Locally, with no owner baked in (`SG_OWNER_SUBJECT`), any signed-in
    user is the owner.
    """
    if config.OWNER_SUBJECT and user.subject != config.OWNER_SUBJECT:
        raise HTTPException(
            status_code=403,
            detail="Only this dashboard's owner can reach its private assets.",
        )
    return user


def _validated(keyvalues: Any, status_code: int = 400) -> Asset:
    """The asset `keyvalues` describe (`build_asset`), or an HTTP error saying why."""
    try:
        return build_asset(keyvalues if isinstance(keyvalues, dict) else {})
    except ValueError as exc:
        raise HTTPException(status_code=status_code, detail=str(exc))


def _require_network(network: str) -> None:
    """Raise 400 for a network that isn't `private` or `public`."""
    if network not in ("private", "public"):
        raise HTTPException(
            status_code=400, detail="network must be 'private' or 'public'"
        )


def public_assets_on() -> bool:
    """Whether this dashboard offers public assets: the org's key, and not off."""
    return config.PUBLIC_ASSETS and bool(os.environ.get("PINATA_JWT"))


def _require_public() -> None:
    """Raise 503 when the dashboard doesn't offer public assets."""
    if not public_assets_on():
        raise HTTPException(
            status_code=503, detail="Shared data isn't available on this deployment."
        )


async def _public_records() -> list[dict]:
    """The cached full public listing, refreshed when older than the TTL.

    Refresh is single-flight: the lock is only contended on a cold/expired
    cache, and the double-check inside it means concurrent misses share one
    Pinata listing instead of each issuing their own.
    """
    global _public_cache

    def _fresh() -> bool:
        """Whether the cache is within its TTL."""
        return (
            _public_cache is not None
            and time.monotonic() - _public_cache[0] <= PUBLIC_CACHE_TTL
        )

    if not _fresh():
        async with _public_cache_lock:
            if not _fresh():
                records = await _pinata().query({})
                _public_cache = (time.monotonic(), records)
    return _public_cache[1]


def forget_public_records() -> None:
    """Drop the cached public listing, so the next read sees a change just made."""
    global _public_cache
    _public_cache = None


SOURCES = ("mine", "public", "stargazer")


async def _source_entries(source: str, filters: dict[str, str]) -> list[dict]:
    """The records `source` holds that carry every keyvalue in `filters`.

    Each comes back stamped with `source`. The owner's index filters in its
    query; the others are in memory already.
    """
    if source == "mine":
        records = await _get_index().query(filters)
    else:
        if source == "public":
            held = await _public_records()
        else:
            held = notebooks.shipped_entries()
        records = [
            r
            for r in held
            if all(r["keyvalues"].get(k) == v for k, v in filters.items())
        ]
    return [{**r, "source": source} for r in records]


@router.get("/assets/schema")
async def assets_schema() -> dict:
    """Registry schema for the dynamic upload form.

    Anonymous-readable: dataclass field names are not sensitive and the
    public tab's type filter wants them too. Notebooks are left out: they're
    published from their workspace tile, not uploaded.
    """
    schema: dict = {}
    for key, cls in sorted(ASSET_REGISTRY.items()):
        if cls is Notebook:
            continue
        hints = get_type_hints(cls)
        schema[key] = [
            {"name": name, "type": getattr(hints.get(name), "__name__", "str")}
            for name in cls.declared_fields()
        ]
    return schema


@router.get("/assets/list")
async def assets_list(request: Request):
    """List the entries of every `source` asked for, filtered by keyvalue params.

    `source` repeats: `mine` (the owner's index rows, newest first; a 401 or
    403 for anyone else), `public` (anonymous, from the TTL cache; a 503
    when the dashboard has no public assets) and `stargazer` (the shipped
    notebooks, anonymous). Every other query param is a keyvalue the entries
    must carry, applied to each source alike. Sources come back in that
    order, each entry carrying its `source`.
    """
    sources = request.query_params.getlist("source")
    if not sources or any(s not in SOURCES for s in sources):
        raise HTTPException(
            status_code=400, detail="source must be 'mine', 'public' or 'stargazer'"
        )
    if "mine" in sources:
        _require_owner(request)
    if "public" in sources:
        _require_public()
    filters = {k: v for k, v in request.query_params.items() if k != "source"}
    entries = []
    for source in (s for s in SOURCES if s in sources):
        entries += await _source_entries(source, filters)
    return entries


@router.post("/assets/update")
async def assets_update(request: Request):
    """Update (merge) metadata on a record the signed-in user owns.

    Fail-closed ownership: the record's current `_owner` must match the
    user's subject (checked server-side, never trusted from the request), so
    nobody can rewrite another user's — or an unowned — record from the page
    even though the Pinata JWT is shared. Ownership is read fresh, not from
    the public TTL cache, so a mutation never decides off stale ownership.
    Validation reuses `build_asset()`, `_owner` is set after it, and Pinata
    merges the patch onto the existing keyvalues (the CID and bytes are
    untouched, so provenance edges survive). A key or value past Pinata's
    length limit is a 400, raised before the request. SDK/MCP edits stay
    unenforced by design (shared JWT). A private record is the owner's index
    row instead (`_update_private`).
    """
    body = await request.json()
    cid = body.get("cid", "")
    keyvalues = body.get("keyvalues") or {}
    network = body.get("network", "public")
    _require_network(network)
    if not cid:
        raise HTTPException(status_code=400, detail="cid is required")
    if network == "private":
        return await _update_private(request, cid, keyvalues)
    _require_public()
    user = _require_user(request)

    records = await _pinata().query({})
    current = next((r for r in records if r["cid"] == cid), None)
    if current is None or current["keyvalues"].get("_owner") != user.subject:
        raise HTTPException(status_code=403, detail="you can only edit assets you own")

    _validated(keyvalues)
    patch = {**keyvalues, "_owner": user.subject}
    try:
        return await _pinata().update_metadata(cid, patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/assets/download/{cid}")
async def assets_download(request: Request, cid: str):
    """Hand back a file's bytes.

    Public files live on world-readable IPFS, so anyone gets a redirect to
    PINATA_GATEWAY, signed in or not, and the bytes never transit the pod.
    Private files stream from the owner's store (`_download_private`). A
    shipped notebook (`network=stargazer`) is its file in the image, to
    anyone.
    """
    network = request.query_params.get("network", "public")
    if network == "stargazer":
        return _download_shipped(cid)
    _require_network(network)
    if network == "private":
        return await _download_private(request, cid)
    gateway = os.environ["PINATA_GATEWAY"]
    return RedirectResponse(f"{gateway}/ipfs/{cid}", status_code=302)


def _download_shipped(cid: str) -> FileResponse:
    """A shipped notebook's file as an attachment, or a 404."""
    path = notebooks.shipped_path(cid)
    if path is None:
        raise HTTPException(status_code=404, detail=f"no shipped notebook {cid}")
    return FileResponse(path, filename=path.name)


async def _download_private(request: Request, cid: str) -> StreamingResponse:
    """Stream one of the owner's stored files back as an attachment.

    Streamed through the dashboard rather than redirected to a presigned
    store URL: the same code serves a local store and the bucket, and needs
    nothing beyond the read the pod's role already has.
    """
    _require_owner(request)
    row = await _get_index().get(cid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no private asset {cid}")

    async def body():
        """The stored file's bytes, chunk by chunk."""
        async for chunk in flyte.storage.get_stream(row["uri"]):
            yield chunk

    name = row["name"].replace('"', "")
    return StreamingResponse(
        body(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


async def _update_private(request: Request, cid: str, keyvalues: dict) -> dict:
    """Merge a validated patch onto the owner's index row, restamping `_owner`."""
    _require_owner(request)
    _validated(keyvalues)
    try:
        return await _get_index().merge(cid, _stamp_owner(dict(keyvalues)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class _LocalWriter:
    """A local file written from async code, for a store rooted at a plain path.

    `flyte.storage.open` only writes object stores; a local run's store is a
    directory.
    """

    def __init__(self, path: Path) -> None:
        """Open `path` for writing, creating its directory."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("wb")

    async def write(self, data: bytes) -> None:
        """Append `data`."""
        await asyncio.to_thread(self._fh.write, data)

    async def close(self) -> None:
        """Finish the file."""
        await asyncio.to_thread(self._fh.close)


async def _open_writer(uri: str) -> Any:
    """A writer for `uri`: a multipart upload on an object store, else a file."""
    if "file" in flyte.storage.get_underlying_filesystem(path=uri).protocol:
        return _LocalWriter(Path(uri))
    return await flyte.storage.open(uri, "wb")


@dataclasses.dataclass
class _TusUpload:
    """One upload in progress: who's sending it, where to, and how far it got.

    A private upload has a `writer` onto the owner's store at `uri`; a public
    one has the URL of Pinata's TUS upload, `pinata_url`.
    """

    subject: str
    length: int
    asset: Asset
    uri: str = ""
    writer: Any = None
    pinata_url: str = ""
    builder: CidBuilder = dataclasses.field(default_factory=CidBuilder)
    offset: int = 0
    touched: float = dataclasses.field(default_factory=time.monotonic)
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)


# Uploads live in the dashboard's memory: the dashboard is one replica, and a
# restart means starting an upload again.
_tus_uploads: dict[str, _TusUpload] = {}


def _tus(status_code: int, **headers: str) -> Response:
    """An empty TUS response carrying the protocol version."""
    return Response(
        status_code=status_code, headers={"Tus-Resumable": TUS_VERSION, **headers}
    )


def _drop_idle_uploads() -> None:
    """Forget uploads no request has touched for `TUS_IDLE_SECONDS`."""
    now = time.monotonic()
    for upload_id, upload in list(_tus_uploads.items()):
        if now - upload.touched > TUS_IDLE_SECONDS:
            del _tus_uploads[upload_id]


def _check_room(upload: _TusUpload, size: int) -> None:
    """A 400 when `size` more bytes would run past `Upload-Length`."""
    if upload.offset + size > upload.length:
        raise HTTPException(status_code=400, detail="More bytes than Upload-Length")


def _count(upload: _TusUpload, piece: bytes) -> None:
    """Take `piece` as received: into the CID and the offset."""
    upload.builder.update(piece)
    upload.offset += len(piece)
    upload.touched = time.monotonic()


def _tus_done(upload: _TusUpload, cid: str | None) -> Response:
    """The reply to a piece: the new offset, and the CID once the file's whole."""
    headers = {"Upload-Offset": str(upload.offset)}
    if cid:
        headers["Stargazer-Cid"] = cid
    return _tus(204, **headers)


def _tus_metadata(header: str) -> dict[str, str]:
    """Decode `Upload-Metadata`: comma-separated `key base64(value)` pairs."""
    pairs = (p.strip().partition(" ") for p in header.split(",") if p.strip())
    try:
        return {k: base64.b64decode(v, validate=True).decode() for k, _, v in pairs}
    except binascii.Error, UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Upload-Metadata isn't valid")


def _store_client() -> StorageClient:
    """A storage client on the owner's store and index, for indexing uploads."""
    return StorageClient(
        local_dir=Path(tempfile.gettempdir()) / "stargazer-uploads",
        store_root=os.environ["STARGAZER_STORE_ROOT"],
        index=_get_index(),
    )


def _tus_upload(request: Request, upload_id: str) -> _TusUpload:
    """The upload in progress under `upload_id`, if the request may send it.

    Only whoever started an upload may continue it. Unknown or expired is a
    404.
    """
    user = _require_user(request)
    _drop_idle_uploads()
    upload = _tus_uploads.get(upload_id)
    if upload is None:
        raise HTTPException(
            status_code=404, detail="This upload has expired; start it again."
        )
    if user.subject != upload.subject:
        raise HTTPException(status_code=403, detail="This isn't your upload.")
    return upload


@router.post("/assets/tus")
async def tus_create(request: Request) -> Response:
    """Start a resumable upload (TUS creation).

    `Upload-Length` is the file's size, at most `TUS_MAX_BYTES`, and
    `Upload-Metadata` carries the `filename`, the `network` (`private`, the
    default, or `public`) and the `keyvalues` (a JSON object), checked with
    `build_asset()` before any bytes move. A private upload is the owner's
    and opens a writer onto their store, as one multipart upload. A public
    one is any signed-in user's, stamped as its `_owner`, and creates
    Pinata's TUS upload, which checks the stamped keyvalues against Pinata's
    limits first. Returns the upload's URL in `Location`.
    """
    user = _require_user(request)
    _drop_idle_uploads()
    try:
        length = int(request.headers.get("Upload-Length", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Upload-Length is required")
    if length <= 0:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if length > TUS_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Uploads are capped at {TUS_MAX_BYTES // 1024**3} GB.",
        )
    meta = _tus_metadata(request.headers.get("Upload-Metadata", ""))
    filename = meta.get("filename", "")
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="filename is required")
    network = meta.get("network", "private")
    _require_network(network)
    if network == "private":
        _check_owner(user)
    else:
        _require_public()
    try:
        keyvalues = json.loads(meta.get("keyvalues", "{}"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    asset = _validated(keyvalues, status_code=422)
    upload_id = uuid.uuid4().hex
    upload = _TusUpload(subject=user.subject, length=length, asset=asset)
    if network == "private":
        upload.uri = _store_client().staging_uri(upload_id, filename)
        upload.writer = await _open_writer(upload.uri)
    else:
        stamped = {**asset.to_keyvalues(), "_owner": user.subject}
        try:
            upload.pinata_url = await _pinata().tus_create(filename, stamped, length)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    _tus_uploads[upload_id] = upload
    return _tus(201, Location=f"/assets/tus/{upload_id}")


@router.head("/assets/tus/{upload_id}")
async def tus_head(request: Request, upload_id: str) -> Response:
    """How much of an upload has arrived, for a client resuming it."""
    upload = _tus_upload(request, upload_id)
    return _tus(
        200,
        **{
            "Upload-Offset": str(upload.offset),
            "Upload-Length": str(upload.length),
            "Cache-Control": "no-store",
        },
    )


@router.patch("/assets/tus/{upload_id}")
async def tus_patch(request: Request, upload_id: str) -> Response:
    """Append the request body to an upload at `Upload-Offset`.

    A private piece goes to the store and the CID builder as it arrives, and
    the offset counts each piece written, so a dropped connection resumes
    from what landed; the piece that completes the file finishes the
    multipart upload and indexes it (`StorageClient.adopt`). A public piece
    goes on to Pinata (`_patch_public`). A wrong offset is a 409. The
    response to the piece that completes the file carries its CID in
    `Stargazer-Cid`.
    """
    upload = _tus_upload(request, upload_id)
    if request.headers.get("Content-Type") != "application/offset+octet-stream":
        raise HTTPException(
            status_code=415, detail="Send application/offset+octet-stream"
        )
    async with upload.lock:
        if request.headers.get("Upload-Offset") != str(upload.offset):
            return _tus(409, **{"Upload-Offset": str(upload.offset)})
        if upload.pinata_url:
            return await _patch_public(request, upload_id, upload)
        async for piece in request.stream():
            _check_room(upload, len(piece))
            await upload.writer.write(piece)
            _count(upload, piece)
        cid = None
        if upload.offset == upload.length:
            del _tus_uploads[upload_id]
            await upload.writer.close()
            cid = upload.builder.cid()
            await _store_client().adopt(upload.asset, upload.uri, cid)
    return _tus_done(upload, cid)


async def _patch_public(
    request: Request, upload_id: str, upload: _TusUpload
) -> Response:
    """Pass one piece of a public upload on to Pinata as one `PATCH`.

    The piece is held whole, at most `TUS_CHUNK_BYTES`, and counted only once
    Pinata has it, so a resume starts from what Pinata has too. The piece
    that completes the file has to come back with the CID worked out here;
    if Pinata's differs, its file is deleted and the upload fails with a 422,
    which the browser doesn't retry.
    """
    chunk = bytearray()
    async for piece in request.stream():
        chunk += piece
        _check_room(upload, len(chunk))
        if len(chunk) > TUS_CHUNK_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Send pieces of at most {TUS_CHUNK_BYTES} bytes.",
            )
    chunk = bytes(chunk)
    stored_cid = await _pinata().tus_patch(upload.pinata_url, upload.offset, chunk)
    _count(upload, chunk)
    cid = None
    if upload.offset == upload.length:
        del _tus_uploads[upload_id]
        cid = upload.builder.cid()
        if stored_cid != cid:
            if stored_cid:
                await _pinata().delete(Asset(cid=stored_cid))
            raise HTTPException(
                status_code=422,
                detail="The upload didn't arrive intact, so it was removed. "
                "Try it again.",
            )
    return _tus_done(upload, cid)
