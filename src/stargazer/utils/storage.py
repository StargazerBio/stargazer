"""
### Storage client.

Where asset bytes and metadata live, and the local cache in front of them.

- **Bytes** go to an object store through `flyte.storage`: a local directory
  when run locally, the user bucket on Union, reached as the user's own
  role. Each file is stored once per user at
  `<STARGAZER_STORE_ROOT>/users/<owner>/assets/<cid>/<name>`, where the
  owner is `STARGAZER_OWNER` (the Union subject) or `local`. A file uploaded
  in pieces, whose CID is known only at the end, stays where it was written,
  `users/<owner>/uploads/<upload id>/<name>`, and its row points there.
- **Metadata** goes to the asset index (`stargazer.utils.index`), one row
  per CID, written after the bytes so a row never points at a missing file.
  A write that doesn't land raises; nothing is retried behind the caller's
  back.
- **Public data** lives on Pinata's public network. When `PINATA_JWT` is
  set, `query()` merges Pinata's public records in (the user's own row wins
  on a shared CID), and public files download from the IPFS gateway.
  `companions()` decides which public companions join the user's own.
- **The cache** is `<STARGAZER_LOCAL>/<cid>/<name>`. Uploads seed it,
  downloads fill it, and `Asset.fetch()` hardlinks companions next to their
  asset. A file named by its own CID never changes; a companion linked into
  its asset's directory is relinked when a later fetch picks a different
  file of that name.

`get_client()` builds a client from the environment; `default_client` is the
lazily built process-wide instance (`_LazyClient`).

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import asyncio
import os
import shutil
from pathlib import Path

import aiofiles
import aiohttp
import flyte.storage
from flyte.io import File

import stargazer.config  # ensure env var defaults are set  # noqa: F401
from stargazer.assets.asset import Asset
from stargazer.utils.cid import compute_cid
from stargazer.utils.index import SqlIndex, make_index
from stargazer.utils.pinata import PinataClient, _stamp_owner
from stargazer.utils.query import generate_query_combinations


def _owner() -> str:
    """The folder name for this user's files: `STARGAZER_OWNER`, or `local`."""
    owner = os.environ.get("STARGAZER_OWNER") or "local"
    if "/" in owner or owner in (".", ".."):
        raise ValueError(f"STARGAZER_OWNER can't be a path: {owner!r}")
    return owner


def _materialize(src: Path, dest: Path) -> None:
    """Place `src` at `dest`, hardlinking when possible; keep an existing `dest`."""
    if dest.exists() or src.resolve() == dest.resolve():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def _makedirs(uri: str) -> None:
    """Create a directory under a local store root; a no-op on object stores."""
    flyte.storage.get_underlying_filesystem(path=uri).makedirs(uri, exist_ok=True)


def _set_stored(asset: Asset, cid: str, uri: str, name: str) -> None:
    """Point `asset` at its stored file."""
    asset.cid = cid
    asset.path = File(path=uri, name=name, hash=cid)


def _remove(uri: str) -> None:
    """Delete one stored file; an absent file is already deleted."""
    try:
        flyte.storage.get_underlying_filesystem(path=uri).rm(uri)
    except FileNotFoundError:
        pass


async def _fetch_http(url: str, dest: Path) -> None:
    """Stream a URL to `dest`.

    aiohttp rather than `flyte.storage`: flyte's HTTP filesystem can't read
    an `https://` path outside a task ("Timeout context manager should be
    used inside a task").
    """
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        response.raise_for_status()
        async with aiofiles.open(dest, "wb") as fh:
            async for chunk in response.content.iter_chunked(1024 * 1024):
                await fh.write(chunk)


class StorageClient:
    """Object-store bytes, an asset index, an optional public tier, a local cache.

    Usage:
        client = get_client()
        await client.upload(asset, Path("s1.bam"))  # sets asset.cid and asset.path
        local = await client.download(asset)        # <local_dir>/<cid>/s1.bam
        rows = await client.query({"asset": "alignment", "sample_id": "S1"})
    """

    def __init__(
        self,
        local_dir: Path,
        store_root: str,
        index: SqlIndex,
        public: PinataClient | None = None,
        gateway: str | None = None,
    ):
        """Wire the client.

        Args:
            local_dir: Scratch space for task outputs and the download cache
            store_root: Object-store root (a local directory or a bucket URI)
            index: The asset index
            public: Pinata client for the public tier, or None for none
            gateway: IPFS gateway for public downloads (defaults to PINATA_GATEWAY)
        """
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.store_root = store_root.rstrip("/")
        self.index = index
        self.public = public
        self.gateway = (gateway or os.environ["PINATA_GATEWAY"]).rstrip("/")

    def _cache_path(self, cid: str, name: str) -> Path:
        """Where a file lives in the local cache."""
        return self.local_dir / cid / name

    def gateway_uri(self, cid: str) -> str:
        """Where the public IPFS gateway serves `cid`."""
        return f"{self.gateway}/ipfs/{cid}"

    def _public_record(self, record: dict) -> dict:
        """A Pinata public record in index-row shape, located at the gateway."""
        cid = record["cid"]
        return {
            "cid": cid,
            "uri": self.gateway_uri(cid),
            "name": record.get("name") or cid,
            "keyvalues": record.get("keyvalues", {}),
        }

    async def upload(self, asset: Asset, path: Path) -> None:
        """Store `path` as `asset`: bytes to the store, then the index row.

        Sets `asset.cid` and `asset.path` (a File at the stored location) and
        seeds the local cache. Bytes the CID's row already points at, or
        already at the target path, aren't transferred again. Whatever the
        store or the index raises propagates: a row that doesn't land fails
        the upload.
        """
        path = Path(path)
        cid = await asyncio.to_thread(compute_cid, path)
        uri, name = await self._stored_copy(cid)
        if uri is None:
            uri, name = (
                f"{self.store_root}/users/{_owner()}/assets/{cid}/{path.name}",
                path.name,
            )
            if not await flyte.storage.exists(uri):
                await asyncio.to_thread(_makedirs, uri.rsplit("/", 1)[0])
                await flyte.storage.put(str(path), uri)
        await self._index_as(asset, cid, uri, name)
        _materialize(path, self._cache_path(cid, name))

    async def _index_as(self, asset: Asset, cid: str, uri: str, name: str) -> None:
        """Write `asset`'s row, stamped with `_owner`, and point it at `uri`."""
        await self.index.upsert(
            {
                "cid": cid,
                "uri": uri,
                "name": name,
                "keyvalues": _stamp_owner(asset.to_keyvalues()),
            }
        )
        _set_stored(asset, cid, uri, name)

    async def _stored_copy(self, cid: str) -> tuple[str | None, str | None]:
        """The `(uri, name)` of the file the CID's row points at, if it exists."""
        row = await self.index.get(cid)
        if row is not None and await flyte.storage.exists(row["uri"]):
            return row["uri"], row["name"]
        return None, None

    def staging_uri(self, upload_id: str, name: str) -> str:
        """Where a file uploaded in pieces is written, before its CID is known."""
        return f"{self.store_root}/users/{_owner()}/uploads/{upload_id}/{name}"

    async def adopt(self, asset: Asset, uri: str, cid: str) -> None:
        """Index a file already written to the store at `uri` as `asset`.

        For bytes that reached the store some other way than `upload`, such as
        a resumable upload from the browser, whose CID was worked out as they
        passed. When the user already has the CID stored, that copy and its
        row stay as they are and `uri` is deleted. Otherwise the row points at
        `uri`, stamped with `_owner` like any upload. Sets `asset.cid` and
        `asset.path` either way.
        """
        stored, name = await self._stored_copy(cid)
        if stored is not None and stored != uri:
            await asyncio.to_thread(_remove, uri)
            _set_stored(asset, cid, stored, name)
        else:
            await self._index_as(asset, cid, uri, uri.rsplit("/", 1)[-1])

    async def download(self, asset: Asset, directory: Path | None = None) -> Path:
        """Make a local copy of `asset` and return its path.

        The copy lives at `<local_dir>/<cid>/<name>`; with `directory` it is
        also linked into that directory (how companions land beside their
        asset), replacing a different file of the same name there. An asset with no CID is a local file that was never stored:
        it is returned in place. An asset with a CID but no file is located
        through the index, or failing that the public IPFS gateway, and its
        `path` is set to what was found.

        Raises:
            FileNotFoundError: when the asset has neither a file nor a CID, or
                no CID and its local file doesn't exist
        """
        if asset.path is None:
            if not asset.cid:
                raise FileNotFoundError("Asset has neither a file nor a CID")
            row = await self.index.get(asset.cid)
            if row is not None:
                asset.path = File(path=row["uri"], name=row["name"], hash=asset.cid)
            else:
                asset.path = File(
                    path=self.gateway_uri(asset.cid), name=asset.cid, hash=asset.cid
                )
        source = asset.path.path
        if not asset.cid:
            local = Path(source)
            if not local.exists():
                raise FileNotFoundError(f"{source} doesn't exist and has no CID")
            return local

        name = asset.path.name or source.rstrip("/").rsplit("/", 1)[-1]
        own = self._cache_path(asset.cid, name)
        if not own.exists():
            if Path(source).exists():
                _materialize(Path(source), own)
            else:
                own.parent.mkdir(parents=True, exist_ok=True)
                part = own.with_name(own.name + ".part")
                if source.startswith(("http://", "https://")):
                    await _fetch_http(source, part)
                else:
                    await flyte.storage.get(source, str(part))
                part.rename(own)
        if directory is None:
            return own
        target = Path(directory) / name
        # The directory is named for another asset's CID, so a file already
        # at `target` may be a different companion of the same name, linked
        # by an earlier fetch.
        if target.exists() and not target.samefile(own):
            target.unlink()
        _materialize(own, target)
        return target

    async def query(self, filters: dict) -> list[dict]:
        """Records matching every filter: the user's rows, then public-only ones.

        Args:
            filters: Keyvalue filters; a list value matches any of its entries

        Returns:
            Rows with `cid`, `uri`, `name` and `keyvalues`
        """
        rows = await self.index.query(filters)
        if self.public is None:
            return rows
        mine = {r["cid"] for r in rows}
        public: dict[str, dict] = {}
        for combo in generate_query_combinations(filters):
            for record in await self.public.query(combo):
                if record["cid"] not in mine:
                    public.setdefault(record["cid"], self._public_record(record))
        return [*rows, *public.values()]

    async def companions(self, cid: str) -> list[dict]:
        """Records whose `companion_of` is `cid`, from the caller and the publisher.

        The user's own rows come first, then public companions the caller
        published (`_owner` is `STARGAZER_OWNER`), so one published earlier
        and no longer in the store is fetched again. Then come public
        companions from whoever published `cid` itself; a file nobody
        published has no publisher to follow. Anyone else's are left out, so
        two publishers' builds of a popular reference never mix. A name
        already taken isn't taken again: a user's own `.bwt` stands, and the
        publisher's fills in only what the user lacks.

        Returns:
            Rows with `cid`, `uri`, `name` and `keyvalues`
        """
        rows = await self.index.query({"companion_of": cid})
        if self.public is None:
            return rows
        records = await self.public.query({"companion_of": cid})
        if not records:
            return rows
        parent = await self.public.get(cid)
        caller = os.environ.get("STARGAZER_OWNER")
        owners = [caller, parent["keyvalues"]["_owner"] if parent else None]
        taken = {row["name"] for row in rows}
        for owner in filter(None, owners):
            for record in records:
                public = self._public_record(record)
                if record["keyvalues"].get("_owner") == owner and (
                    public["name"] not in taken
                ):
                    taken.add(public["name"])
                    rows.append(public)
        return rows

    async def delete(self, asset: Asset) -> None:
        """Remove the asset's index row and, if it's in the store, its file.

        A row pointing at the IPFS gateway (a fetched bundle) has no stored
        file to remove. Idempotent.
        """
        row = await self.index.get(asset.cid)
        await self.index.delete(asset.cid)
        if row is not None and not row["uri"].startswith(("http://", "https://")):
            await asyncio.to_thread(_remove, row["uri"])

    async def publish(self, cid: str) -> dict:
        """Put one of the user's stored assets on the public tier, same CID.

        Uploads the stored file to Pinata's public network with its index
        row's keyvalues; `_owner` is restamped from `STARGAZER_OWNER`, as on
        any upload, and files over 100 MB go up in resumable chunks. The
        user's row stays, so the asset is in both tiers, and `query` keeps
        the row over the public duplicate.

        Args:
            cid: The stored asset to publish

        Returns:
            The public record: `cid`, `name` and `keyvalues`

        Raises:
            ValueError: with no public tier, for a CID that isn't in the
                user's index, for keyvalues over Pinata's limits (before
                anything is sent), or when Pinata assigns a different CID
        """
        if self.public is None:
            raise ValueError("No PINATA_JWT: there's no public tier to publish to")
        row = await self.index.get(cid)
        if row is None:
            raise ValueError(f"{cid} isn't in your storage")
        stored = Asset(cid=cid, path=File(path=row["uri"], name=row["name"], hash=cid))
        local = await self.download(stored)
        published = Asset(keyvalues=_stamp_owner(dict(row["keyvalues"])))
        await self.public.upload(published, local)
        # Our CIDs are computed to match Pinata's, so a mismatch is a bug.
        if published.cid != cid:
            raise ValueError(
                f"Pinata stored {cid} as {published.cid}; the CIDs should match"
            )
        return {
            "cid": cid,
            "name": row["name"],
            "keyvalues": published.to_keyvalues(),
        }

    async def update_metadata(self, cid: str, keyvalues: dict[str, str]) -> dict:
        """Merge a metadata patch onto the user's index row, restamping `_owner`.

        Args:
            cid: The record to update
            keyvalues: Keys to add or overwrite; others are kept

        Raises:
            ValueError: when the user has no row for `cid`
        """
        return await self.index.merge(cid, _stamp_owner(dict(keyvalues)))


def get_client() -> StorageClient:
    """Build a storage client from the environment.

    `STARGAZER_STORE_ROOT`, `STARGAZER_INDEX_URL` and `STARGAZER_LOCAL` pick
    the store, the index and the cache; `PINATA_JWT` turns on the public
    tier.
    """
    return StorageClient(
        local_dir=Path(os.environ["STARGAZER_LOCAL"]),
        store_root=os.environ["STARGAZER_STORE_ROOT"],
        index=make_index(os.environ["STARGAZER_INDEX_URL"]),
        public=PinataClient() if os.environ.get("PINATA_JWT") else None,
    )


class _LazyClient:
    """Lazy singleton proxy for the storage client.

    PINATA_JWT is injected by Flyte just before a task runs, so building the
    client at import would miss it and silently drop the public tier.
    """

    _instance: StorageClient | None = None

    def _resolve(self) -> StorageClient:
        """Construct the real client on first use and memoize it."""
        if self._instance is None:
            self._instance = get_client()
        return self._instance

    def __getattr__(self, name: str):
        """Proxy every attribute access to the lazily-resolved client."""
        return getattr(self._resolve(), name)


default_client: StorageClient = _LazyClient()  # type: ignore[assignment]
