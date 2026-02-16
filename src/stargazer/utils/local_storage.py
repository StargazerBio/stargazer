"""
Local filesystem storage client for Stargazer.

Stores files locally with TinyDB metadata indexing. No network access required.
"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tinydb import TinyDB, Query

from stargazer.utils.ipfile import IpFile


class LocalStorageClient:
    """
    Local filesystem storage client.

    Stores files in a local directory and indexes metadata in TinyDB.
    No network access or API credentials required.

    Usage:
        client = LocalStorageClient()
        file = await client.upload_file(Path("data.bam"), keyvalues={"type": "alignment"})
        files = await client.query_files({"type": "alignment"})
        await client.download_file(file)
    """

    def __init__(
        self,
        local_dir: Optional[Path] = None,
    ):
        """
        Initialize local storage client.

        Args:
            local_dir: Local directory for file storage (defaults to STARGAZER_LOCAL env var
                       or ~/.stargazer/local)
        """
        self.local_dir = local_dir or Path(
            os.environ.get("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))
        )
        self.local_dir.mkdir(parents=True, exist_ok=True)

        # TinyDB for local metadata storage (lazy initialized)
        self.local_db_path = self.local_dir / "stargazer_local.json"
        self._db: Optional[TinyDB] = None

    @property
    def db(self) -> TinyDB:
        """Get TinyDB instance for local metadata storage (lazy initialized)."""
        if self._db is None:
            self._db = TinyDB(self.local_db_path)
        return self._db

    async def upload_file(
        self,
        path: Path,
        keyvalues: Optional[dict[str, str]] = None,
        public: Optional[bool] = None,
    ) -> IpFile:
        """
        Copy a file to local storage and index metadata in TinyDB.

        Args:
            path: Local file path to store
            keyvalues: Metadata key-value pairs for querying
            public: Visibility flag (stored in metadata but no functional difference locally)

        Returns:
            IpFile with local CID and metadata
        """
        is_public = public if public is not None else False

        local_cid = f"local_{path.name}_{path.stat().st_size}"

        # Copy to local dir
        local_path = self.local_dir / local_cid
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, local_path)

        # Store metadata in TinyDB
        now = datetime.now(timezone.utc)
        self.db.insert(
            {
                "id": local_cid,
                "cid": local_cid,
                "name": path.name,
                "size": path.stat().st_size,
                "keyvalues": keyvalues or {},
                "created_at": now.isoformat(),
                "is_public": is_public,
                "rel_path": local_cid,
            }
        )

        return IpFile(
            id=local_cid,
            cid=local_cid,
            name=path.name,
            size=path.stat().st_size,
            keyvalues=keyvalues or {},
            created_at=now,
            is_public=is_public,
            local_path=local_path,
        )

    async def download_file(
        self, ipfile: IpFile, dest: Optional[Path] = None
    ) -> IpFile:
        """
        Resolve a local file path. For local storage, files are already on disk.

        Args:
            ipfile: IpFile object to resolve
            dest: Optional destination path (copies file there)

        Returns:
            Updated IpFile with local_path set
        """
        # Skip if local_path is already set and file exists
        if ipfile.local_path and ipfile.local_path.exists():
            return ipfile

        cid = ipfile.cid

        # Check local dir first (cache key)
        cache_key = cid.replace("/", "_")
        cache_path = self.local_dir / cache_key

        if cache_path.exists():
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(cache_path, dest)
                ipfile.local_path = dest
            else:
                ipfile.local_path = cache_path
            return ipfile

        # Look up in TinyDB for path resolution
        if cid.startswith("local_"):

            File = Query()
            record = self.db.get(File.cid == cid)
            if record:
                local_path = self.local_dir / record["rel_path"]
                if local_path.exists():
                    if dest:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(local_path, dest)
                        ipfile.local_path = dest
                    else:
                        ipfile.local_path = local_path
                    return ipfile
            raise FileNotFoundError(
                f"Local file {cid} not found in local directory or database."
            )

        raise FileNotFoundError(
            f"File {cid} not found in local storage. "
            "Use a PinataClient for remote files."
        )

    async def query_files(
        self, keyvalues: dict[str, str], public: Optional[bool] = None
    ) -> list[IpFile]:
        """
        Query files by keyvalue metadata from TinyDB.

        Args:
            keyvalues: Metadata key-value pairs to filter by
            public: Ignored for local storage

        Returns:
            List of matching IpFile objects
        """
        results = []
        for record in self.db.all():
            record_kv = record.get("keyvalues", {})
            if all(record_kv.get(k) == v for k, v in keyvalues.items()):
                results.append(self._ipfile_from_db_record(record))
        return results

    async def delete_file(self, ipfile: IpFile) -> None:
        """
        Delete a file from local storage and TinyDB.

        Args:
            ipfile: IpFile object to delete
        """

        File = Query()
        record = self.db.get(File.cid == ipfile.cid)
        if record:
            local_path = self.local_dir / record["rel_path"]
            if local_path.exists():
                local_path.unlink()
            self.db.remove(File.cid == ipfile.cid)

    def _ipfile_from_db_record(self, record: dict) -> IpFile:
        """Convert a TinyDB record to an IpFile object."""
        return IpFile(
            id=record["id"],
            cid=record["cid"],
            name=record.get("name"),
            size=record["size"],
            keyvalues=record.get("keyvalues", {}),
            created_at=datetime.fromisoformat(record["created_at"]),
            local_path=self.local_dir / record["rel_path"],
            is_public=record.get("is_public", False),
        )
