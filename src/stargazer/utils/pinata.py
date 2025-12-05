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
import asyncio
from dataclasses import dataclass
from datetime import datetime
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
    ):
        """
        Initialize Pinata client.

        Args:
            jwt: Pinata JWT token (defaults to PINATA_JWT env var)
            gateway: IPFS gateway URL (defaults to gateway.pinata.cloud)
            cache_dir: Local cache directory for downloads
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
        Upload a file to Pinata.

        Args:
            path: Local file path
            keyvalues: Metadata key-value pairs for querying

        Returns:
            IpFile with CID and metadata
        """
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

    async def download_file(self, cid: str, dest: Optional[Path] = None) -> Path:
        """
        Download a file by CID via IPFS gateway.
        Uses local cache to avoid re-downloading.

        Args:
            cid: IPFS CID
            dest: Optional destination path

        Returns:
            Path to downloaded file
        """
        import shutil

        # Check cache first
        cache_key = cid.replace("/", "_")
        cache_path = self.cache_dir / cache_key

        if cache_path.exists():
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(cache_path, dest)
                return dest
            return cache_path

        # Try multiple gateways in case of rate limiting
        gateways = [
            self.gateway,
            "https://ipfs.io",
            "https://cloudflare-ipfs.com",
            "https://dweb.link",
        ]

        # Set timeout for the request (60 seconds total, 10 seconds for connection)
        timeout = aiohttp.ClientTimeout(total=60, connect=10)

        last_error = None
        for gateway in gateways:
            url = f"{gateway}/ipfs/{cid}"

            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
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
            raise last_error or Exception("All IPFS gateways failed")

        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(cache_path, dest)
            return dest

        return cache_path

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

        if keyvalues:
            params["metadata"] = json.dumps(keyvalues)

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
