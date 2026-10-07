"""
### Storage client.

Where asset bytes and metadata live, and the local cache in front of them.

- **Bytes** go to an object store through `flyte.storage`: a local directory
  on a laptop, the tenant bucket on Union. Each file is stored once per user
  at `<STARGAZER_STORE_ROOT>/users/<owner>/assets/<cid>/<name>`, where the
  owner is `STARGAZER_OWNER` (the Union subject) or `local`.
- **Metadata** goes to the asset index (`stargazer.utils.index`), one row
  per CID, written after the bytes so a row never points at a missing file.
  A write that doesn't land raises; nothing is retried behind the caller's
  back.
- **Public data** lives on Pinata's public network. When `PINATA_JWT` is
  set, `query()` merges Pinata's public records in (the user's own row wins
  on a shared CID), and public files download from the IPFS gateway.
- **The cache** is `<STARGAZER_LOCAL>/<cid>/<name>`. Uploads seed it,
  downloads fill it, and `Asset.fetch()` hardlinks companions next to their
  asset.

Gateway downloads use aiohttp directly: `flyte.io.File.download()` can't
read an `https://` path (flyte 2.10.7's HTTP filesystem fails with "Timeout
context manager should be used inside a task").

`get_client()` builds a client from the environment; `default_client` is the
lazily built process-wide instance (lazy because Flyte injects `PINATA_JWT`
just before a task runs).

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
from stargazer.utils.index import SqliteIndex
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


def _remove(uri: str) -> None:
    """Delete one stored file; an absent file is already deleted."""
    try:
        flyte.storage.get_underlying_filesystem(path=uri).rm(uri)
    except FileNotFoundError:
        pass


async def _fetch_http(url: str, dest: Path) -> None:
    """Stream a URL to `dest`."""
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
        index: SqliteIndex,
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

    def _public_record(self, record: dict) -> dict:
        """A Pinata public record in index-row shape, located at the gateway."""
        cid = record["cid"]
        return {
            "cid": cid,
            "uri": f"{self.gateway}/ipfs/{cid}",
            "name": record.get("name") or cid,
            "keyvalues": record.get("keyvalues", {}),
        }

    async def upload(self, asset: Asset, path: Path) -> None:
        """Store `path` as `asset`: bytes to the store, then the index row.

        Sets `asset.cid` and `asset.path` (a File at the stored location) and
        seeds the local cache. Identical bytes already in the store aren't
        transferred again.

        Raises:
            Whatever the store or the index raises; a row that doesn't land
            fails the upload.
        """
        path = Path(path)
        cid = await asyncio.to_thread(compute_cid, path)
        uri = f"{self.store_root}/users/{_owner()}/assets/{cid}/{path.name}"
        if not await flyte.storage.exists(uri):
            await asyncio.to_thread(_makedirs, uri.rsplit("/", 1)[0])
            await flyte.storage.put(str(path), uri)
        await self.index.upsert(
            {
                "cid": cid,
                "uri": uri,
                "name": path.name,
                "keyvalues": _stamp_owner(asset.to_keyvalues()),
            }
        )
        asset.cid = cid
        asset.path = File(path=uri, name=path.name, hash=cid)
        _materialize(path, self._cache_path(cid, path.name))

    async def download(self, asset: Asset, directory: Path | None = None) -> Path:
        """Make a local copy of `asset` and return its path.

        The copy lives at `<local_dir>/<cid>/<name>`; with `directory` it is
        also linked into that directory (how companions land beside their
        asset). An asset with no CID is a local file that was never stored:
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
                uri = f"{self.gateway}/ipfs/{asset.cid}"
                asset.path = File(path=uri, name=asset.cid, hash=asset.cid)
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
        for combo in generate_query_combinations(base_query={}, filters=filters):
            for record in await self.public.query(combo, network="public"):
                if record["cid"] not in mine:
                    public.setdefault(record["cid"], self._public_record(record))
        return [*rows, *public.values()]

    async def get(self, cid: str) -> dict | None:
        """The user's index row for `cid`, or None."""
        return await self.index.get(cid)

    async def delete(self, asset: Asset) -> None:
        """Remove the asset's index row and its stored file. Idempotent."""
        row = await self.index.get(asset.cid)
        await self.index.delete(asset.cid)
        if row is not None:
            await asyncio.to_thread(_remove, row["uri"])

    async def update_metadata(
        self, cid: str, keyvalues: dict[str, str], network: str | None = None
    ) -> dict:
        """Merge a metadata patch onto a record, restamping `_owner`.

        Args:
            cid: The record to update
            keyvalues: Keys to add or overwrite; others are kept
            network: "public" edits the Pinata public record; otherwise the
                user's index row

        Raises:
            ValueError: when the record doesn't exist, or "public" is asked
                for without a Pinata key
        """
        if network == "public":
            if self.public is None:
                raise ValueError("No PINATA_JWT: public records can't be edited")
            return await self.public.update_metadata(cid, keyvalues, network="public")
        return await self.index.merge(cid, _stamp_owner(dict(keyvalues)))


def make_index(url: str) -> SqliteIndex:
    """The index named by `STARGAZER_INDEX_URL`: a SQLite file path.

    A `sqlite://` prefix is accepted and stripped; `~` is expanded.
    """
    return SqliteIndex(Path(url.removeprefix("sqlite://")).expanduser())


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

    Why: PINATA_JWT is injected by Flyte just before a task runs, so building
    the client at import would miss it and silently drop the public tier.
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
