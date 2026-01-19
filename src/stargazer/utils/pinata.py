"""
Pinata API v3 client for IPFS file storage.

Provides async interface for:
- Uploading files with keyvalue metadata
- Downloading files via IPFS gateway with local caching
- Querying files by keyvalue pairs
- Deleting files
"""

import os
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles
from tinydb import TinyDB


@dataclass
class IpFile:
    """Represents a file stored in IPFS (via Pinata or other service)."""

    id: str
    cid: str
    name: Optional[str]
    size: int
    keyvalues: dict[str, str]
    created_at: datetime
    local_path: Optional[Path] = None  # Local cached file path
    is_public: bool = False  # Whether file is on public IPFS (vs private Pinata)

    @classmethod
    def from_api_response(cls, data: dict) -> "IpFile":
        """Parse from Pinata API JSON response."""
        # Determine visibility from network field (defaults to private if not present)
        network = data.get("network", "private")
        is_public = network == "public"

        return cls(
            id=data["id"],
            cid=data["cid"],
            name=data.get("name"),
            size=data["size"],
            keyvalues=data.get("keyvalues", {}),
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            local_path=None,
            is_public=is_public,
        )

    def public_url(self, gateway: str = "https://ipfs.io") -> Optional[str]:
        """Get public gateway URL. Returns None if file is private."""
        if self.is_public:
            return f"{gateway}/ipfs/{self.cid}"
        return None


class PinataClient:
    """
    Simplified async client for Pinata API v3.

    Usage:
        client = PinataClient()

        # Upload with metadata (visibility controlled by STARGAZER_PUBLIC env var)
        file = await client.upload_file(
            Path("data.bam"),
            keyvalues={"type": "alignment", "sample": "NA12878"}
        )

        # Upload explicitly as public
        file = await client.upload_file(Path("data.bam"), public=True)

        # Query by keyvalues
        files = await client.query_files({"type": "alignment", "sample": "NA12878"})

        # Download (uses appropriate gateway based on file.is_public)
        await client.download_file(file)

        # Delete file
        await client.delete_file(file)
    """

    API_BASE = "https://api.pinata.cloud/v3"
    UPLOAD_BASE = "https://uploads.pinata.cloud/v3"

    def __init__(
        self,
        jwt: Optional[str] = None,
        gateway: Optional[str] = None,
        local_dir: Optional[Path] = None,
        local_only: Optional[bool] = None,
        public: Optional[bool] = None,
    ):
        """
        Initialize Pinata client.

        Args:
            jwt: Pinata JWT token (defaults to PINATA_JWT env var)
            gateway: IPFS gateway URL (defaults to gateway.pinata.cloud)
            local_dir: Local directory for file storage and caching
            local_only: If True, copy files to local dir instead of uploading to IPFS
                       (defaults to STARGAZER_LOCAL_ONLY env var)
            public: If True, upload files to public IPFS network
                   (defaults to STARGAZER_PUBLIC env var)
        """
        self._jwt = jwt or os.environ.get("PINATA_JWT")
        self.gateway = gateway or os.environ.get(
            "PINATA_GATEWAY", "https://gateway.pinata.cloud"
        )
        self.local_dir = local_dir or Path(
            os.environ.get("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))
        )
        self.local_dir.mkdir(parents=True, exist_ok=True)

        # Check for local_only mode from env var if not explicitly set
        if local_only is None:
            local_only_env = os.environ.get("STARGAZER_LOCAL_ONLY", "").lower()
            self.local_only = local_only_env in ("1", "true", "yes")
        else:
            self.local_only = local_only

        # Check for public mode from env var if not explicitly set
        if public is None:
            public_env = os.environ.get("STARGAZER_PUBLIC", "").lower()
            self.public = public_env in ("1", "true", "yes")
        else:
            self.public = public

        # TinyDB for local metadata storage (lazy initialized)
        self.local_db_path = self.local_dir / "stargazer_local.json"
        self._db: Optional[TinyDB] = None

    @property
    def db(self) -> TinyDB:
        """Get TinyDB instance for local metadata storage (lazy initialized)."""
        if self._db is None:
            self._db = TinyDB(self.local_db_path)
        return self._db

    @property
    def jwt(self) -> str:
        """Get JWT token, raising error if not set."""
        if not self._jwt:
            raise ValueError(
                "PINATA_JWT not set. Provide jwt= argument or "
                "set PINATA_JWT environment variable."
            )
        return self._jwt

    def _headers(self) -> dict:
        """Get authorization headers."""
        return {"Authorization": f"Bearer {self.jwt}"}

    async def upload_file(
        self,
        path: Path,
        keyvalues: Optional[dict[str, str]] = None,
        public: Optional[bool] = None,
    ) -> IpFile:
        """
        Upload a file to Pinata.

        Behavior depends on self.local_only (set via STARGAZER_LOCAL_ONLY env var):
        - If False (default): Upload to IPFS via Pinata
        - If True: Copy to local cache without uploading

        Visibility depends on public parameter or self.public (STARGAZER_PUBLIC env var):
        - If True: Upload to public IPFS (accessible via any gateway)
        - If False (default): Upload to private Pinata (requires JWT to access)

        Args:
            path: Local file path
            keyvalues: Metadata key-value pairs for querying
            public: Override default visibility (None uses self.public)

        Returns:
            IpFile with CID and metadata
        """
        # Determine visibility: explicit param > instance default
        is_public = public if public is not None else self.public

        if self.local_only:
            # Local-only mode: copy to cache without uploading
            local_cid = f"local_{path.name}_{path.stat().st_size}"

            # Copy to local dir
            cache_path = self.local_dir / local_cid
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, cache_path)

            # Create IpFile object for local reference
            return IpFile(
                id=local_cid,
                cid=local_cid,
                name=path.name,
                size=path.stat().st_size,
                keyvalues=keyvalues or {},
                created_at=datetime.now(timezone.utc),
                is_public=is_public,
            )

        # Upload to IPFS via Pinata
        url = f"{self.UPLOAD_BASE}/files"

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", open(path, "rb"), filename=path.name)
            data.add_field("name", path.name)
            data.add_field("network", "public" if is_public else "private")

            if keyvalues:
                data.add_field("keyvalues", json.dumps(keyvalues))

            async with session.post(
                url, headers=self._headers(), data=data
            ) as response:
                response.raise_for_status()
                result = await response.json()
                print(result)
                return IpFile.from_api_response(result.get("data", result))

    async def download_file(
        self, ipfile: IpFile, dest: Optional[Path] = None
    ) -> IpFile:
        """
        Download a file and update IpFile with local path.
        Uses local cache to avoid re-downloading.

        Download strategy based on file visibility:
        - Public files: Use ipfs.io gateway (no auth required)
        - Private files: Use Pinata gateway (requires JWT)

        Args:
            ipfile: IpFile object to download
            dest: Optional destination path (otherwise uses cache)

        Returns:
            Updated IpFile with path set to downloaded file location
        """
        # Skip download if local_path is already set and file exists
        if ipfile.local_path and ipfile.local_path.exists():
            return ipfile

        cid = ipfile.cid

        # Check local dir first
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

        # Local CIDs must be in cache
        if cid.startswith("local_"):
            raise FileNotFoundError(
                f"Local file {cid} not found in cache. It may have been deleted."
            )

        # Select gateway based on file visibility
        if ipfile.is_public:
            # Public files: use ipfs.io, no auth needed
            gateway_url = f"https://ipfs.io/ipfs/{cid}"
            headers = {}
        else:
            # Private files: use Pinata gateway with auth
            gateway_url = f"{self.gateway}/ipfs/{cid}"
            headers = self._headers()

        async with aiohttp.ClientSession() as session:
            async with session.get(gateway_url, headers=headers) as response:
                response.raise_for_status()

                cache_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(cache_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(cache_path, dest)
            ipfile.local_path = dest
        else:
            ipfile.local_path = cache_path

        return ipfile

    async def query_files(
        self, keyvalues: dict[str, str], public: Optional[bool] = None
    ) -> list[IpFile]:
        """
        Query files by keyvalue metadata.

        Args:
            keyvalues: Metadata key-value pairs to filter by
            public: Query public or private files (None queries based on self.public)

        Returns:
            List of matching IpFile objects

        Example:
            files = await client.query_files({"type": "reference", "build": "GRCh38"})
        """
        is_public = public if public is not None else self.public
        network = "public" if is_public else "private"
        url = f"{self.API_BASE}/files/{network}"
        params = {"pageLimit": 1000, "order": "DESC"}

        # Add metadata filters using the correct format: metadata[key]=value
        if keyvalues:
            for key, value in keyvalues.items():
                params[f"metadata[{key}]"] = value

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=self._headers(), params=params
            ) as response:
                response.raise_for_status()
                data = await response.json()

                return [
                    IpFile.from_api_response(f)
                    for f in data.get("data", {}).get("files", [])
                ]

    async def delete_file(self, ipfile: IpFile) -> None:
        """
        Delete a file from Pinata.

        Args:
            ipfile: IpFile object to delete
        """
        network = "public" if ipfile.is_public else "private"
        url = f"{self.API_BASE}/files/{network}/{ipfile.id}"

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=self._headers()) as response:
                response.raise_for_status()


# Default module-level client instance
# Configured via environment variables:
# - PINATA_JWT: Pinata JWT token (required for uploads and private downloads)
# - PINATA_GATEWAY: IPFS gateway URL (default: https://gateway.pinata.cloud)
# - STARGAZER_LOCAL: Local directory for files (default: ~/.stargazer/local)
# - STARGAZER_LOCAL_ONLY: If "1"/"true"/"yes", copy files locally instead of uploading
# - STARGAZER_PUBLIC: If "1"/"true"/"yes", upload files to public IPFS (default: private)
default_client = PinataClient()
