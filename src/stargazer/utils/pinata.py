"""
# Pinata API v3 client for IPFS file storage.

Provides async interface for:
- Uploading files with keyvalue metadata
- Downloading files via IPFS gateway with local caching
- Querying files by keyvalue pairs
- Deleting files

spec: [docs/architecture/modes.md](../architecture/modes.md)
"""

import os
import json
import shutil
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles

from stargazer.types.asset import Asset


class PinataClient:
    """
    Async client for Pinata API v3.

    Used when STARGAZER_MODE=local and PINATA_JWT is available.
    Handles uploads to IPFS via Pinata, downloads via IPFS gateways,
    and metadata queries against the Pinata API.

    Usage:
        client = PinataClient()

        # Upload with metadata
        comp = Asset(path=Path("data.bam"), keyvalues={"type": "alignment"})
        await client.upload(comp)  # sets comp.cid

        # Query by keyvalues
        files = await client.query({"type": "alignment", "sample": "NA12878"})

        # Download
        await client.download(comp)  # sets comp.path

        # Delete file
        await client.delete(comp)
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
        """Get JWT token, raising error if not set.
        """
        if not self._jwt:
            raise ValueError(
                "PINATA_JWT not set. Provide jwt= argument or "
                "set PINATA_JWT environment variable."
            )
        return self._jwt

    def _headers(self) -> dict:
        """Get authorization headers.
        """
        return {"Authorization": f"Bearer {self.jwt}"}

    async def _get_gateway_domain(self) -> str:
        """Fetch the dedicated gateway domain from Pinata API.
        """
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
        """Get a signed download URL for a private file.
        """
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

    async def upload(self, component: Asset) -> None:
        """
        Upload a file to IPFS via Pinata. Sets component.cid.

        Args:
            component: Asset with path and keyvalues set
        """
        path = component.path
        if path is None:
            raise ValueError("component.path must be set before uploading")

        url = f"{self.UPLOAD_BASE}/files"

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", open(path, "rb"), filename=path.name)
            data.add_field("name", path.name)
            data.add_field("network", "private")

            if component.keyvalues:
                data.add_field("keyvalues", json.dumps(component.keyvalues))

            async with session.post(
                url, headers=self._headers(), data=data
            ) as response:
                response.raise_for_status()
                result = await response.json()
                data_obj = result.get("data", result)
                component.cid = data_obj["cid"]

    async def download(self, component: Asset, dest: Optional[Path] = None) -> None:
        """
        Download a file from IPFS and set component.path.
        Uses local cache to avoid re-downloading.

        Args:
            component: Asset with cid set
            dest: Optional destination path (otherwise uses cache)
        """
        # Skip download if path is already set and file exists
        if component.path and component.path.exists():
            return

        cid = component.cid

        # Check local dir first
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
            component.path = dest
        else:
            component.path = cache_path

    async def query(self, keyvalues: dict[str, str]) -> list[Asset]:
        """
        Query files by keyvalue metadata from Pinata API.
        Paginates through all results automatically.

        Args:
            keyvalues: Metadata key-value pairs to filter by

        Returns:
            List of matching Asset objects
        """
        url = f"{self.API_BASE}/files/private"
        params: dict = {"pageLimit": 1000, "order": "DESC"}

        # Add metadata filters using the correct format: metadata[key]=value
        if keyvalues:
            for key, value in keyvalues.items():
                params[f"metadata[{key}]"] = value

        results: list[Asset] = []
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.get(
                    url, headers=self._headers(), params=params
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    for f in data.get("data", {}).get("files", []):
                        results.append(
                            Asset(
                                cid=f["cid"],
                                keyvalues=f.get("keyvalues", {}),
                            )
                        )

                    next_token = data.get("data", {}).get("next_page_token")
                    if not next_token:
                        break
                    params["pageToken"] = next_token

        return results

    async def delete(self, component: Asset) -> None:
        """
        Delete a file from Pinata by querying for its internal ID first.

        Args:
            component: Asset with cid set
        """
        url = f"{self.API_BASE}/files/private"
        params = {"cid": component.cid}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=self._headers(), params=params
            ) as response:
                response.raise_for_status()
                data = await response.json()
                files = data.get("data", {}).get("files", [])
                if not files:
                    return
                file_id = files[0]["id"]

            async with session.delete(
                f"{self.API_BASE}/files/private/{file_id}",
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
