"""
### Pinata API v3 client for IPFS file storage.

Provides async interface for authenticated Pinata operations:
- Uploading files with keyvalue metadata
- Downloading private files via signed gateway URLs
- Querying files by keyvalue pairs
- Deleting files

Used as a remote backend by LocalStorageClient when PINATA_JWT is available.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles

import stargazer.config  # ensure env var defaults are set  # noqa: F401

from stargazer.assets.asset import Asset


class PinataClient:
    """Async client for Pinata API v3.

    Handles authenticated operations against the Pinata API: uploads,
    private downloads via signed URLs, metadata queries, and deletions.

    This is a pure remote transport — caching is handled by LocalStorageClient.

    PINATA_VISIBILITY controls upload network and query/download behavior:
    - "private": uploads as private, downloads via signed URLs, queries /files/private
    - "public": uploads as public, downloads via public gateway (handled by
      LocalStorageClient), queries /files/public

    If JWT is unset, only public downloads are possible (via LocalStorageClient's
    public gateway fallback).

    Usage:
        client = PinataClient()
        comp = Asset(path=Path("data.bam"), keyvalues={"type": "alignment"})
        await client.upload(comp)  # sets comp.cid
        files = await client.query({"type": "alignment", "sample": "NA12878"})
        await client.delete(comp)
    """

    API_BASE = "https://api.pinata.cloud/v3"
    UPLOAD_BASE = "https://uploads.pinata.cloud/v3"

    def __init__(
        self,
        jwt: Optional[str] = None,
        visibility: Optional[str] = None,
    ):
        """Initialize Pinata client.

        Args:
            jwt: Pinata JWT token (defaults to PINATA_JWT from config)
            visibility: "public" or "private" (defaults to PINATA_VISIBILITY from config)
        """
        self._jwt = jwt or os.environ.get("PINATA_JWT") or None
        self.visibility = visibility or os.environ["PINATA_VISIBILITY"]

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
        """Upload a file to IPFS via Pinata. Sets component.cid.

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
            data.add_field("network", self.visibility)

            kv = component.to_keyvalues()
            if kv:
                data.add_field("keyvalues", json.dumps(kv))

            async with session.post(
                url, headers=self._headers(), data=data
            ) as response:
                response.raise_for_status()
                result = await response.json()
                data_obj = result.get("data", result)
                component.cid = data_obj["cid"]

    async def download_to(self, cid: str, dest: Path) -> None:
        """Download a file to dest. Uses signed URL for private, raises for public.

        Public downloads are handled by LocalStorageClient's public gateway
        fallback, so this method is only called for private visibility.

        Args:
            cid: Content identifier
            dest: Destination path to write to
        """
        if self.visibility == "public":
            raise ValueError(
                "Public downloads should use the public IPFS gateway, "
                "not signed URLs. This is a bug — LocalStorageClient "
                "should have handled this download."
            )

        download_url = await self._get_signed_url(cid)

        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                response.raise_for_status()

                dest.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(dest, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

    async def query(self, keyvalues: dict[str, str]) -> list[dict]:
        """Query files by keyvalue metadata from Pinata API.

        Checks both private and public Pinata endpoints and merges results
        by CID so files are found regardless of which network they were
        uploaded to.

        Args:
            keyvalues: Metadata key-value pairs to filter by

        Returns:
            List of matching file records with cid, name, and keyvalues
        """
        seen: dict[str, dict] = {}
        for visibility in ("private", "public"):
            url = f"{self.API_BASE}/files/{visibility}"
            params: dict = {"pageLimit": 1000, "order": "DESC"}
            if keyvalues:
                for key, value in keyvalues.items():
                    params[f"keyvalues[{key}]"] = value

            async with aiohttp.ClientSession() as session:
                while True:
                    async with session.get(
                        url, headers=self._headers(), params=params
                    ) as response:
                        response.raise_for_status()
                        data = json.loads(await response.text())

                        for f in data.get("data", {}).get("files", []):
                            if f["cid"] not in seen:
                                seen[f["cid"]] = {
                                    "cid": f["cid"],
                                    "name": f.get("name", ""),
                                    "keyvalues": f.get("keyvalues", {}),
                                }

                        next_token = data.get("data", {}).get("next_page_token")
                        if not next_token:
                            break
                        params["pageToken"] = next_token

        return list(seen.values())

    async def delete(self, component: Asset) -> None:
        """Delete a file from Pinata by querying for its internal ID first.

        Args:
            component: Asset with cid set
        """
        url = f"{self.API_BASE}/files/{self.visibility}"
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
                f"{self.API_BASE}/files/{self.visibility}/{file_id}",
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
