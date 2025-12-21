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
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles


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

    @classmethod
    def from_api_response(cls, data: dict) -> "IpFile":
        """Parse from Pinata API JSON response."""
        return cls(
            id=data["id"],
            cid=data["cid"],
            name=data.get("name"),
            size=data["size"],
            keyvalues=data.get("keyvalues", {}),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            local_path=None,  # Set when file is downloaded
        )


class PinataClient:
    """
    Simplified async client for Pinata API v3.

    Usage:
        client = PinataClient()

        # Upload with metadata
        file = await client.upload_file(
            Path("data.bam"),
            keyvalues={"type": "alignment", "sample": "NA12878"}
        )

        # Query by keyvalues
        files = await client.query_files({"type": "alignment", "sample": "NA12878"})

        # Download by CID
        local_path = await client.download_file(file.cid)

        # Delete by file ID
        await client.delete_file(file.id)
    """

    API_BASE = "https://api.pinata.cloud/v3"
    UPLOAD_BASE = "https://uploads.pinata.cloud/v3"

    def __init__(
        self,
        jwt: Optional[str] = None,
        gateway: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        local_only: Optional[bool] = None,
    ):
        """
        Initialize Pinata client.

        Args:
            jwt: Pinata JWT token (defaults to PINATA_JWT env var)
            gateway: IPFS gateway URL (defaults to gateway.pinata.cloud)
            cache_dir: Local cache directory for downloads
            local_only: If True, copy files to cache instead of uploading to IPFS
                       (defaults to STARGAZER_LOCAL_ONLY env var)
        """
        self._jwt = jwt or os.environ.get("PINATA_JWT")
        self.gateway = gateway or os.environ.get(
            "PINATA_GATEWAY",
            "https://gateway.pinata.cloud"
        )
        self.cache_dir = cache_dir or Path(
            os.environ.get("STARGAZER_CACHE", str(Path.home() / ".stargazer" / "cache"))
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Check for local_only mode from env var if not explicitly set
        if local_only is None:
            local_only_env = os.environ.get("STARGAZER_LOCAL_ONLY", "").lower()
            self.local_only = local_only_env in ("1", "true", "yes")
        else:
            self.local_only = local_only

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
    ) -> IpFile:
        """
        Upload a file to Pinata or copy to local cache.

        Behavior depends on self.local_only (set via STARGAZER_LOCAL_ONLY env var):
        - If False (default): Upload to IPFS via Pinata
        - If True: Copy to local cache without uploading

        Args:
            path: Local file path
            keyvalues: Metadata key-value pairs for querying

        Returns:
            IpFile with CID and metadata
        """
        if self.local_only:
            # Local-only mode: copy to cache without uploading
            local_cid = f"local_{path.name}_{path.stat().st_size}"

            # Copy to cache
            cache_path = self.cache_dir / local_cid
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
            )
        else:
            # Upload to IPFS via Pinata
            url = f"{self.UPLOAD_BASE}/files"

            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', open(path, 'rb'), filename=path.name)
                data.add_field('name', path.name)

                if keyvalues:
                    data.add_field('keyvalues', json.dumps(keyvalues))

                async with session.post(url, headers=self._headers(), data=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return IpFile.from_api_response(result.get("data", result))

    async def download_file(self, ipfile: IpFile, dest: Optional[Path] = None) -> IpFile:
        """
        Download a file using Pinata API and update IpFile with local path.
        Uses local cache to avoid re-downloading.

        Args:
            ipfile: IpFile object to download
            dest: Optional destination path (otherwise uses cache)

        Returns:
            Updated IpFile with path set to downloaded file location
        """
        import shutil
        import time

        cid = ipfile.cid

        # Check cache first
        cache_key = cid.replace("/", "_")
        cache_path = self.cache_dir / cache_key

        if cache_path.exists():
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(cache_path, dest)
                ipfile.local_path = dest
            else:
                ipfile.local_path = cache_path
            return ipfile

        # If it's a local CID (from local_only mode), it should already be in cache
        if cid.startswith("local_"):
            raise FileNotFoundError(
                f"Local file {cid} not found in cache. It may have been deleted."
            )

        # Try multiple IPFS gateways in case of issues
        # Start with Pinata, then fall back to public gateways
        gateways = [
            f"{self.gateway}/ipfs/{cid}",
            f"https://ipfs.io/ipfs/{cid}",
            f"https://cloudflare-ipfs.com/ipfs/{cid}",
            f"https://dweb.link/ipfs/{cid}",
        ]

        # Set timeout for the request (30 seconds total, 10 seconds for connection)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        last_error = None
        for gateway_url in gateways:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    # Use auth for Pinata gateway, no auth for public gateways
                    use_auth = gateway_url.startswith(self.gateway)
                    headers = self._headers() if (use_auth and self._jwt) else {}

                    async with session.get(gateway_url, headers=headers) as response:
                        response.raise_for_status()

                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        async with aiofiles.open(cache_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)

                        # Success! Break out of gateway loop
                        break

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                # Try next gateway
                continue
        else:
            # All gateways failed
            raise Exception(f"Failed to download file from all IPFS gateways. Last error: {last_error}")

        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(cache_path, dest)
            ipfile.local_path = dest
        else:
            ipfile.local_path = cache_path

        return ipfile

    async def query_files(self, keyvalues: dict[str, str]) -> list[IpFile]:
        """
        Query files by keyvalue metadata.

        Args:
            keyvalues: Metadata key-value pairs to filter by

        Returns:
            List of matching IpFile objects

        Example:
            files = await client.query_files({"type": "reference", "build": "GRCh38"})
        """
        url = f"{self.API_BASE}/files/private"
        params = {"pageLimit": 1000, "order": "DESC"}

        # Add metadata filters using the correct format: metadata[key]=value
        if keyvalues:
            for key, value in keyvalues.items():
                params[f"metadata[{key}]"] = value

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._headers(),
                params=params
            ) as response:
                response.raise_for_status()
                data = await response.json()

                return [
                    IpFile.from_api_response(f)
                    for f in data.get("data", {}).get("files", [])
                ]

    async def delete_file(self, file_id: str) -> None:
        """
        Delete a file from Pinata by its file ID.

        Args:
            file_id: Pinata file ID (not CID)
        """
        url = f"{self.API_BASE}/files/private/{file_id}"

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=self._headers()) as response:
                response.raise_for_status()


# Default module-level client instance
# Configured via environment variables:
# - PINATA_JWT: Pinata JWT token
# - PINATA_GATEWAY: IPFS gateway URL (default: https://gateway.pinata.cloud)
# - STARGAZER_CACHE: Local cache directory (default: ~/.stargazer/cache)
# - STARGAZER_LOCAL_ONLY: If set to "1", "true", or "yes", copy files locally instead of uploading to IPFS
default_client = PinataClient()
