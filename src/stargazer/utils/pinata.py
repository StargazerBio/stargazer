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
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles

from stargazer.utils.ipfile import IpFile


class PinataClient:
    """
    Async client for Pinata API v3.

    Used when STARGAZER_MODE=local and PINATA_JWT is available.
    Handles uploads to IPFS via Pinata, downloads via IPFS gateways,
    and metadata queries against the Pinata API.

    Usage:
        client = PinataClient()

        # Upload with metadata
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
    ):
        """
        Initialize Pinata client.

        Args:
            jwt: Pinata JWT token (defaults to PINATA_JWT env var)
            gateway: IPFS gateway URL (defaults to gateway.pinata.cloud)
            local_dir: Local directory for download caching
        """
        self._jwt = jwt or os.environ.get("PINATA_JWT")
        self.gateway = gateway or os.environ.get(
            "PINATA_GATEWAY", "https://gateway.pinata.cloud"
        )
        self.local_dir = local_dir or Path(
            os.environ.get("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))
        )
        self.local_dir.mkdir(parents=True, exist_ok=True)

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

    async def _get_gateway_domain(self) -> str:
        """Fetch the dedicated gateway domain from Pinata API."""
        if not hasattr(self, "_gateway_domain") or self._gateway_domain is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.API_BASE}/ipfs/gateways", headers=self._headers()
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    rows = data["data"]["rows"]
                    if not rows:
                        raise ValueError(
                            "No gateway configured in Pinata account. "
                            "Create one at https://app.pinata.cloud/gateway"
                        )
                    domain = rows[0]["domain"]
                    self._gateway_domain = f"https://{domain}.mypinata.cloud"
        return self._gateway_domain

    async def _get_signed_url(self, cid: str, expires: int = 300) -> str:
        """Get a signed download URL for a private file."""
        import time

        gateway = await self._get_gateway_domain()
        payload = {
            "url": f"{gateway}/files/{cid}",
            "expires": expires,
            "date": int(time.time()),
            "method": "GET",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.API_BASE}/files/sign",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data["data"]

    async def upload_file(
        self,
        path: Path,
        keyvalues: Optional[dict[str, str]] = None,
        public: Optional[bool] = None,
    ) -> IpFile:
        """
        Upload a file to IPFS via Pinata.

        Args:
            path: Local file path
            keyvalues: Metadata key-value pairs for querying
            public: If True, upload to public IPFS. If False/None, upload as private.

        Returns:
            IpFile with CID and metadata
        """
        is_public = public if public is not None else False

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
        Download a file from IPFS and update IpFile with local path.
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

        # Select download strategy based on file visibility
        if ipfile.is_public:
            # Public files: use ipfs.io gateway, no auth needed
            download_url = f"https://ipfs.io/ipfs/{cid}"
        else:
            # Private files: get a signed URL via Pinata API
            download_url = await self._get_signed_url(cid)

        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
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
        Query files by keyvalue metadata from Pinata API.

        Args:
            keyvalues: Metadata key-value pairs to filter by
            public: Query public or private files (defaults to private)

        Returns:
            List of matching IpFile objects
        """
        is_public = public if public is not None else False
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
