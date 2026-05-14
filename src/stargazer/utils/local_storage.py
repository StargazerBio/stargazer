"""
### Local filesystem storage client for Stargazer.

Always the primary storage client. Stores files locally with TinyDB metadata
indexing and delegates to a remote backend (PinataClient) or the public IPFS
gateway for cache misses.

Also provides the module-level factory and singleton:
- ``get_client()``: create a ``LocalStorageClient`` based on available config
- ``default_client``: pre-built singleton used across the application

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles
from tinydb import TinyDB, Query

import stargazer.config  # ensure env var defaults are set  # noqa: F401

from stargazer.assets.asset import Asset
from stargazer.utils.pinata import PinataClient


class LocalStorageClient:
    """Local filesystem storage client with optional remote backend.

    Always handles caching and TinyDB metadata. Downloads follow this order:

    1. Return if file already exists at component.path
    2. Check local cache by CID
    3. If remote backend (PinataClient) is attached, fetch via signed URL
    4. Fall back to public IPFS gateway

    When a PinataClient remote is attached, upload/query/delete delegate to it.
    Without a remote, upload/query/delete operate locally only.

    Usage:
        client = LocalStorageClient()
        comp = Asset(path=Path("data.bam"), keyvalues={"type": "alignment"})
        await client.upload(comp)
        files = await client.query({"type": "alignment"})
        await client.download(comp)
    """

    def __init__(
        self,
        local_dir: Optional[Path] = None,
        remote: Optional[PinataClient] = None,
        public_gateway: Optional[str] = None,
    ):
        """Initialize local storage client.

        Args:
            local_dir: Local directory for file storage (defaults to STARGAZER_LOCAL)
            remote: Optional PinataClient for authenticated Pinata operations
            public_gateway: Public IPFS gateway URL (defaults to PINATA_GATEWAY)
        """
        self.local_dir = local_dir or Path(os.environ["STARGAZER_LOCAL"])
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.remote = remote
        self.public_gateway = (
            public_gateway
            if public_gateway is not None
            else os.environ["PINATA_GATEWAY"]
        )

        # TinyDB for local metadata storage (lazy initialized)
        self.local_db_path = self.local_dir / "stargazer_local.json"
        self._db: Optional[TinyDB] = None
        self._db_mtime: float = 0.0

    @property
    def db(self) -> TinyDB:
        """Get TinyDB instance for local metadata storage (lazy initialized).

        Re-opens if the DB file has been deleted or modified externally,
        keeping _last_id in sync when other processes write to the same file.
        """
        mtime = (
            self.local_db_path.stat().st_mtime if self.local_db_path.exists() else 0.0
        )
        if self._db is None or mtime != self._db_mtime:
            if self._db is not None:
                self._db.close()
            self._db = TinyDB(self.local_db_path)
            self._db_mtime = mtime
        return self._db

    async def upload(self, component: Asset) -> None:
        """Upload a file. Delegates to remote if attached, otherwise stores locally.

        Args:
            component: Asset with path and keyvalues set
        """
        if self.remote:
            await self.remote.upload(component)
            return

        path = component.path
        if path is None:
            raise ValueError("component.path must be set before uploading")

        # Generate MD5 hash of file content (streamed to handle large files)
        h = hashlib.md5()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        md5_hash = h.hexdigest()
        cid = f"local_{md5_hash}"

        # Determine relative path: preserve subdirectory if file is inside local_dir
        try:
            rel_path = path.resolve().relative_to(self.local_dir.resolve())
        except ValueError:
            rel_path = Path(path.name)

        local_path = self.local_dir / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != local_path.resolve():
            shutil.copy2(path, local_path)

        # Upsert metadata in TinyDB (avoid duplicates on re-upload)
        now = datetime.now(timezone.utc)
        File = Query()
        self.db.upsert(
            {
                "cid": cid,
                "keyvalues": component.to_keyvalues(),
                "created_at": now.isoformat(),
                "rel_path": str(rel_path),
            },
            File.cid == cid,
        )

        component.cid = cid

    async def download(
        self,
        component: Asset,
        dest: Optional[Path] = None,
    ) -> bool:
        """Download a file by CID. Checks cache, then remote, then public gateway.

        Args:
            component: Asset with cid set. When ``component.path`` is set,
                its filename is used for the local cache file (so the file
                lands on disk with its real extension).
            dest: Optional destination path (copies file there)

        Returns:
            True if the file was already cached, False if freshly downloaded.
        """
        # Skip if path is already set and file exists
        if component.path and component.path.exists():
            return True

        cid = component.cid

        # No usable source: nothing on disk and no CID to fetch from. Fail
        # fast here rather than hitting the public gateway with an empty CID
        # (which 500s) or returning False with no file written.
        if not cid:
            raise FileNotFoundError(
                f"Asset has no cid and path does not exist: {component.path}"
            )

        # 1. Cache filename: prefer the caller-supplied path name (preserves
        # extension), fall back to the CID for unnamed downloads.
        cache_key = component.path.name if component.path else cid.replace("/", "_")
        cache_path = self.local_dir / cache_key

        if cache_path.exists():
            self._resolve_dest(component, cache_path, dest)
            return True

        # 2. Check TinyDB for local_ CIDs
        if cid.startswith("local_"):
            File = Query()
            record = self.db.get(File.cid == cid)
            if record:
                local_path = self.local_dir / record["rel_path"]
                if local_path.exists():
                    self._resolve_dest(component, local_path, dest)
                    return True
            raise FileNotFoundError(
                f"Local file {cid} not found in local directory or database."
            )

        # 3. Remote backend (signed URLs for private visibility).
        # On 403 (CID is public, or gateway plan limit hit) attempt the public
        # IPFS gateway. If that also fails, re-raise the original 403 so the
        # caller sees a meaningful error rather than a gateway timeout.
        if self.remote and self.remote.visibility == "private":
            try:
                await self.remote.download_to(cid, cache_path)
                self._resolve_dest(component, cache_path, dest)
                return False
            except aiohttp.ClientResponseError as exc:
                if exc.status != 403:
                    raise
                try:
                    await self._fetch_public(cid, cache_path)
                    self._resolve_dest(component, cache_path, dest)
                    return False
                except aiohttp.ClientResponseError:
                    raise exc

        # 4. Public IPFS gateway (public visibility or no remote)
        await self._fetch_public(cid, cache_path)
        self._resolve_dest(component, cache_path, dest)
        return False

    async def query(self, keyvalues: dict[str, str]) -> list[dict]:
        """Query files by keyvalue metadata. Delegates to remote if attached.

        Args:
            keyvalues: Metadata key-value pairs to filter by

        Returns:
            List of raw storage records with 'cid', 'path', and 'keyvalues' keys
        """
        if self.remote:
            return await self.remote.query(keyvalues)

        results = []
        for record in self.db.all():
            record_kv = record.get("keyvalues", {})
            if all(record_kv.get(k) == v for k, v in keyvalues.items()):
                results.append(
                    {
                        "cid": record["cid"],
                        "name": record.get("name", ""),
                        "path": self.local_dir / record["rel_path"],
                        "keyvalues": record_kv,
                    }
                )
        return results

    async def delete(self, component: Asset) -> None:
        """Delete a file. Delegates to remote if attached, otherwise deletes locally.

        Args:
            component: Asset with cid set
        """
        if self.remote:
            await self.remote.delete(component)
            return

        File = Query()
        record = self.db.get(File.cid == component.cid)
        if record:
            local_path = self.local_dir / record["rel_path"]
            if local_path.exists():
                local_path.unlink()
            self.db.remove(File.cid == component.cid)

    def _resolve_dest(
        self, component: Asset, source: Path, dest: Optional[Path]
    ) -> None:
        """Set component.path, optionally copying to dest."""
        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, dest)
            component.path = dest
        else:
            component.path = source

    async def _fetch_public(self, cid: str, dest: Path) -> None:
        """Fetch a file from the public IPFS gateway.

        Writes to a .tmp sibling first and renames on completion so an
        interrupted download never leaves a truncated file in the cache.
        """
        url = f"{self.public_gateway}/ipfs/{cid}"
        tmp = dest.with_suffix(dest.suffix + ".tmp")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()

                dest.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(tmp, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

        tmp.rename(dest)


def get_client() -> "LocalStorageClient":
    """Create a storage client based on available credentials.

    Always returns a LocalStorageClient. When PINATA_JWT is available,
    a PinataClient remote is attached for authenticated operations (upload,
    query, delete, private downloads). Public IPFS gateway access is always
    available for downloading public CIDs.

    Resolution logic:
        - PINATA_JWT set -> LocalStorageClient + PinataClient remote
        - No JWT -> LocalStorageClient (public gateway only)

    Returns:
        A LocalStorageClient, optionally with a PinataClient remote
    """
    if os.environ.get("PINATA_JWT"):
        return LocalStorageClient(remote=PinataClient())

    return LocalStorageClient()


class _LazyClient:
    """Lazy singleton proxy for the storage client.

    Why: PINATA_JWT is injected by Flyte just before a task runs, so
    eagerly constructing the client at module-import time misses the env
    var and silently degrades to local-only TinyDB. Deferring construction
    until first attribute access guarantees we see the populated env.
    """

    _instance: Optional[LocalStorageClient] = None

    def _resolve(self) -> LocalStorageClient:
        if self._instance is None:
            self._instance = get_client()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)


default_client: LocalStorageClient = _LazyClient()  # type: ignore[assignment]
