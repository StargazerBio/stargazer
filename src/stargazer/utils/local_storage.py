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

from stargazer.utils.component import ComponentFile


class LocalStorageClient:
    """
    Local filesystem storage client.

    Stores files in a local directory and indexes metadata in TinyDB.
    No network access or API credentials required.

    Usage:
        client = LocalStorageClient()
        comp = ComponentFile(path=Path("data.bam"), keyvalues={"type": "alignment"})
        await client.upload(comp)
        files = await client.query({"type": "alignment"})
        await client.download(comp)
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

    async def upload(self, component: ComponentFile) -> None:
        """
        Copy a file to local storage, index metadata in TinyDB, and set component.cid.

        Args:
            component: ComponentFile with path and keyvalues set
        """
        path = component.path
        if path is None:
            raise ValueError("component.path must be set before uploading")

        cid = f"local_{path.name}_{path.stat().st_size}"

        # Copy to local dir
        local_path = self.local_dir / cid
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, local_path)

        # Store metadata in TinyDB
        now = datetime.now(timezone.utc)
        self.db.insert(
            {
                "cid": cid,
                "keyvalues": component.keyvalues,
                "created_at": now.isoformat(),
                "rel_path": cid,
            }
        )

        component.cid = cid

    async def download(
        self, component: ComponentFile, dest: Optional[Path] = None
    ) -> None:
        """
        Resolve a local file path and set component.path. For local storage, files are
        already on disk.

        Args:
            component: ComponentFile with cid set
            dest: Optional destination path (copies file there)
        """
        # Skip if path is already set and file exists
        if component.path and component.path.exists():
            return

        cid = component.cid

        # Check local dir first (cache key)
        cache_key = cid.replace("/", "_")
        cache_path = self.local_dir / cache_key

        if cache_path.exists():
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(cache_path, dest)
                component.path = dest
            else:
                component.path = cache_path
            return

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
                        component.path = dest
                    else:
                        component.path = local_path
                    return
            raise FileNotFoundError(
                f"Local file {cid} not found in local directory or database."
            )

        raise FileNotFoundError(
            f"File {cid} not found in local storage. "
            "Use a PinataClient for remote files."
        )

    async def query(self, keyvalues: dict[str, str]) -> list[ComponentFile]:
        """
        Query files by keyvalue metadata from TinyDB.

        Args:
            keyvalues: Metadata key-value pairs to filter by

        Returns:
            List of matching ComponentFile objects
        """
        results = []
        for record in self.db.all():
            record_kv = record.get("keyvalues", {})
            if all(record_kv.get(k) == v for k, v in keyvalues.items()):
                cid = record["cid"]
                results.append(
                    ComponentFile(
                        cid=cid,
                        path=self.local_dir / record["rel_path"],
                        keyvalues=record.get("keyvalues", {}),
                    )
                )
        return results

    async def delete(self, component: ComponentFile) -> None:
        """
        Delete a file from local storage and TinyDB.

        Args:
            component: ComponentFile with cid set
        """
        File = Query()
        record = self.db.get(File.cid == component.cid)
        if record:
            local_path = self.local_dir / record["rel_path"]
            if local_path.exists():
                local_path.unlink()
            self.db.remove(File.cid == component.cid)
