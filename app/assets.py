"""
### Asset browser API routes.

APIRouter included by the dashboard, serving the asset browser on its home
page (`templates/_assets.html`) over two networks:

- **Private** is the dashboard owner's own asset index and store, the same
  ones their tasks write to. Uploads stream through the dashboard into the
  store (`StorageClient.upload`: the CID, the stored file, the index row),
  downloads stream back out, and metadata edits merge onto the index row.
  Only the owner reaches them: another signed-in user gets a 403.
- **Public** is Pinata's public network, through the org's shared key (a
  Flyte secret, `app.admin_app`). Uploads go browser→Pinata on a signed URL,
  so the bytes never transit the dashboard, and downloads redirect to the
  gateway. Pinata's private network is never used: with a shared key it
  would keep nothing private. Without a key (the devbox, which drops app
  secrets, or a local run with none), or with public assets turned off for
  the deploy (`config.PUBLIC_ASSETS`), the public routes 503 and the
  browser's Public tab says shared data isn't available.

Auth model: Union's login sits in front of these routes, so on the hosted
deploy every request is a signed-in user. The routes still degrade for an
anonymous request (a local run): public browsing works, while private
routes, minting and edits 401. The public listing is served from an
in-process TTL cache so the dashboard acts as a semi-static read-only mirror
rather than an open proxy to the Pinata API. Public edits fail closed: only
a record's `_owner` may change it.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import dataclasses
import json
import os
import tempfile
import time
from pathlib import Path
from typing import get_type_hints

import flyte.storage
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from app import config
from app.identity import User, user_from_request
from app.index_api import _get_index
from stargazer.assets import ASSET_REGISTRY, build_asset
from stargazer.assets.asset import _BASE_FIELDS
from stargazer.utils.pinata import PinataClient, _stamp_owner
from stargazer.utils.storage import StorageClient

router = APIRouter()

# Pinata's plain multipart POST — the only thing a signed URL accepts from
# a fetch() upload — is capped at 100MB; larger files require the TUS
# resumable endpoint (ticket tus-browser-uploads). Mirroring the cap into the
# signed URL turns an opaque mid-upload failure into a mint-time error the
# form can explain. Private uploads share it for now: they stream to the
# dashboard's disk, whose ephemeral-storage limit hasn't been checked.
MAX_UPLOAD_BYTES = 100 * 1024**2

# The anonymous public tab reads this cache, refreshed lazily — stale
# entries cost at most one Pinata listing per TTL regardless of traffic.
PUBLIC_CACHE_TTL = 60.0

# Module attributes resolved at call time so tests can swap in fakes.
_pinata_client: PinataClient | None = None
_public_cache: tuple[float, list[dict]] | None = None
# Single-flight guard for cache refreshes: concurrent anonymous requests on a
# cold/expired cache would otherwise each fan out their own Pinata listing.
_public_cache_lock = asyncio.Lock()


def _pinata() -> PinataClient:
    """The shared Pinata client, created lazily (keeps its gateway cache)."""
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
    """The signed-in user if they own this dashboard, else a 401 or 403.

    Locally, with no owner baked in (`SG_OWNER_SUBJECT`), any signed-in
    user is the owner.
    """
    user = _require_user(request)
    if config.OWNER_SUBJECT and user.subject != config.OWNER_SUBJECT:
        raise HTTPException(
            status_code=403,
            detail="Only this dashboard's owner can reach its private assets.",
        )
    return user


def _require_network(network: str) -> None:
    """Raise 400 for a network that isn't `private` or `public`."""
    if network not in ("private", "public"):
        raise HTTPException(
            status_code=400, detail="network must be 'private' or 'public'"
        )


def _size(n: int) -> str:
    """A byte count in the unit the upload form states its cap in."""
    return f"{n // 1024**2} MB" if n % 1024**2 == 0 else f"{n} bytes"


def public_assets_on() -> bool:
    """Whether this dashboard offers public assets: the org's key, and not off."""
    return config.PUBLIC_ASSETS and bool(os.environ.get("PINATA_JWT"))


def _require_pinata() -> None:
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
        """Whether the cache exists and is within its TTL."""
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


@router.get("/assets/schema")
async def assets_schema() -> dict:
    """Registry schema for the dynamic upload form.

    Anonymous-readable: dataclass field names are not sensitive and the
    public tab's type filter wants them too.
    """
    schema: dict = {}
    for key, cls in sorted(ASSET_REGISTRY.items()):
        hints = get_type_hints(cls)
        schema[key] = [
            {
                "name": f.name,
                "type": getattr(hints.get(f.name), "__name__", "str"),
                "default": (
                    f.default if f.default is not dataclasses.MISSING else None
                ),
            }
            for f in dataclasses.fields(cls)
            if f.name not in _BASE_FIELDS
        ]
    return schema


@router.get("/assets/list")
async def assets_list(request: Request):
    """List assets on one network, filtered by keyvalue query params.

    Private: the owner's index rows, newest first. Public: anonymous, served
    from the TTL cache with filters applied in-process.
    """
    params = dict(request.query_params)
    network = params.pop("network", "public")
    _require_network(network)
    if network == "private":
        _require_owner(request)
        return await _get_index().query(params)
    _require_pinata()
    records = await _public_records()
    return [
        r for r in records if all(r["keyvalues"].get(k) == v for k, v in params.items())
    ]


@router.post("/assets/sign")
async def assets_sign(request: Request):
    """Validate metadata and mint a signed upload URL (signed-in user required).

    `build_asset()` is the same choke point the MCP server uses; the
    user's subject is stamped as `_owner` after validation, so the minted
    URL carries exactly the validated + stamped keyvalues and the browser
    supplies bytes only. More keyvalues than a Pinata file holds is a 400
    here, at mint time, rather than a failed upload in the browser.
    """
    _require_pinata()
    user = _require_user(request)

    body = await request.json()
    filename = body.get("filename", "")
    if body.get("network", "public") != "public":
        raise HTTPException(
            status_code=400,
            detail="Signed uploads are public; private ones post to /assets/upload.",
        )
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    try:
        asset = build_asset(body.get("keyvalues") or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    keyvalues = asset.to_keyvalues()
    keyvalues["_owner"] = user.subject
    try:
        url = await _pinata().create_signed_upload_url(
            filename=filename,
            keyvalues=keyvalues,
            max_file_size=MAX_UPLOAD_BYTES,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url, "keyvalues": keyvalues}


@router.post("/assets/update")
async def assets_update(request: Request):
    """Update (merge) metadata on a record the signed-in user owns.

    Fail-closed ownership: the record's current `_owner` must match the
    user's subject (checked server-side, never trusted from the request), so
    nobody can rewrite another user's — or an unowned — record from the page
    even though the Pinata JWT is shared. Validation reuses `build_asset()`,
    `_owner` is re-stamped after it, and Pinata merges the patch onto the
    existing keyvalues (the CID and bytes are untouched, so provenance edges
    survive). A key or value past Pinata's length limit is a 400, raised
    before the request. SDK/MCP edits stay unenforced by design (shared JWT).
    A private record is the owner's index row instead (`_update_private`).
    """
    body = await request.json()
    cid = body.get("cid", "")
    network = body.get("network", "public")
    _require_network(network)
    if network == "private":
        if not cid:
            raise HTTPException(status_code=400, detail="cid is required")
        return await _update_private(request, cid, body.get("keyvalues") or {})
    _require_pinata()
    user = _require_user(request)
    if not cid:
        raise HTTPException(status_code=400, detail="cid is required")

    # Fail-closed: only the owner of record may edit it. Read fresh (not the
    # public TTL cache) so a mutation never decides off stale ownership.
    records = await _pinata().query({})
    current = next((r for r in records if r["cid"] == cid), None)
    if current is None or current["keyvalues"].get("_owner") != user.subject:
        raise HTTPException(status_code=403, detail="you can only edit assets you own")

    try:
        build_asset(body.get("keyvalues") or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    patch = dict(body.get("keyvalues") or {})
    patch["_owner"] = user.subject
    try:
        return await _pinata().update_metadata(cid, patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/assets/download/{cid}")
async def assets_download(request: Request, cid: str):
    """Hand back a file's bytes.

    Public files live on world-readable IPFS, so anyone gets a redirect to
    PINATA_GATEWAY, signed in or not, and the bytes never transit the pod.
    Private files stream from the owner's store (`_download_private`).
    """
    network = request.query_params.get("network", "public")
    _require_network(network)
    if network == "private":
        return await _download_private(request, cid)
    gateway = os.environ["PINATA_GATEWAY"]
    return RedirectResponse(f"{gateway}/ipfs/{cid}", status_code=302)


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
    try:
        build_asset(keyvalues)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        return await _get_index().merge(cid, _stamp_owner(dict(keyvalues)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/assets/upload")
async def assets_upload(request: Request, filename: str = "", keyvalues: str = "{}"):
    """Store the request body as a private asset in the owner's store and index.

    The keyvalues (a JSON object in the query string) are checked with
    `build_asset()` before any of the body is read. The body streams to a temp
    file, refused past `MAX_UPLOAD_BYTES`, then `StorageClient.upload` works
    out the CID, stores the file and writes the index row, stamping `_owner`.
    Returns the row.
    """
    _require_owner(request)
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="filename is required")
    try:
        parsed = json.loads(keyvalues)
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="keyvalues must be a JSON object")
    try:
        asset = build_asset(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        size = 0
        with path.open("wb") as fh:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Uploads are capped at {_size(MAX_UPLOAD_BYTES)}.",
                    )
                fh.write(chunk)
        # The client's cache sits in the temp dir too, so nothing it links
        # outlives the request on the dashboard's small disk.
        client = StorageClient(
            local_dir=Path(tmp) / "cache",
            store_root=os.environ["STARGAZER_STORE_ROOT"],
            index=_get_index(),
        )
        await client.upload(asset, path)
    return await _get_index().get(asset.cid)
