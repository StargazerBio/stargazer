"""
### Pinata API v3 client for IPFS file storage.

Provides async interface for authenticated Pinata operations:
- Uploading files with keyvalue metadata
- Querying files by keyvalue pairs
- Updating metadata and deleting files
- Minting signed upload and download URLs

Stargazer uses Pinata's public network only: shared data lives there,
readable by everyone and attributed by `_owner`. Every call defaults to it.
The asset-manager page (`app/assets.py`) still passes `network="private"`
for its Private tab until the page moves onto the asset index.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import base64
import json
import os
import time
from pathlib import Path

import aiofiles
import aiohttp

import stargazer.config  # ensure env var defaults are set  # noqa: F401
from stargazer.assets.asset import Asset

# Pinata's plain multipart POST is capped at 100MB; larger files must use the
# resumable TUS endpoint. upload() switches paths at this threshold. Chunks
# must stay under Pinata's 50MB TUS limit; per-file ceiling is 10 GiB.
TUS_THRESHOLD_BYTES = 100 * 1024**2
TUS_CHUNK_BYTES = 48 * 1024**2


def _tus_metadata(filename: str, network: str, keyvalues: dict[str, str]) -> str:
    """Encode TUS ``Upload-Metadata``: comma-joined ``key b64(value)`` pairs.

    Pinata reads ``filename``, ``network``, and ``keyvalues`` (stringified
    JSON) from this header on the creation POST.
    """
    fields = {
        "filename": filename,
        "network": network,
        "keyvalues": json.dumps(keyvalues),
    }
    return ",".join(
        f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in fields.items()
    )


def _stamp_owner(kv: dict[str, str]) -> dict[str, str]:
    """Inject ``_owner`` from STARGAZER_OWNER into upload keyvalues.

    Env wins: a rehydrated record must not carry a stale owner onto the
    re-upload of a derived artifact. With the env unset the dict passes
    through untouched, so manual attribution in scripts stays possible.
    """
    owner = os.environ.get("STARGAZER_OWNER")
    if owner:
        kv["_owner"] = owner
    return kv


class PinataClient:
    """Async client for Pinata API v3.

    Handles authenticated operations against the Pinata API: uploads,
    private downloads via signed URLs, metadata queries, and deletions.

    A pure remote transport: caching and gateway downloads are the storage
    client's job (`stargazer.utils.storage`).

    Every call works on Pinata's public network unless given another
    `network`. Only the asset-manager page still asks for "private".

    Usage:
        client = PinataClient()
        comp = Asset(keyvalues={"asset": "alignment", "sample_id": "NA12878"})
        await client.upload(comp, Path("data.bam"))  # sets comp.cid
        files = await client.query({"asset": "alignment", "sample_id": "NA12878"})
        await client.delete(comp)
    """

    API_BASE = "https://api.pinata.cloud/v3"
    UPLOAD_BASE = "https://uploads.pinata.cloud/v3"

    def __init__(self, jwt: str | None = None):
        """Initialize Pinata client.

        Args:
            jwt: Pinata JWT token (defaults to PINATA_JWT from config)
        """
        self._jwt = jwt or os.environ.get("PINATA_JWT") or None

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
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{self.API_BASE}/ipfs/gateways", headers=self._headers()
                ) as response,
            ):
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
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.API_BASE}/files/sign",
                headers=self._headers(),
                json=payload,
            ) as response,
        ):
            response.raise_for_status()
            data = await response.json()
            return data["data"]

    async def create_signed_upload_url(
        self,
        filename: str,
        keyvalues: dict[str, str],
        network: str,
        expires: int = 300,
        max_file_size: int | None = None,
    ) -> str:
        """Mint a signed upload URL for a direct browser→Pinata upload.

        All metadata is fixed at mint time — Pinata bakes ``filename``,
        ``keyvalues``, and the size cap into the URL, so the uploader
        supplies bytes only and can never attach unvalidated metadata.

        Args:
            filename: Name the uploaded file will carry (downloads resolve
                their on-disk name from it)
            keyvalues: Validated, already-stamped metadata to bake in
            network: "private" or "public"
            expires: URL lifetime in seconds after minting
            max_file_size: Upload size cap in bytes, if any

        Returns:
            The signed upload URL
        """
        payload: dict = {
            "date": int(time.time()),
            "expires": expires,
            "filename": filename,
            "keyvalues": keyvalues,
            "network": network,
        }
        if max_file_size is not None:
            payload["max_file_size"] = max_file_size

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.UPLOAD_BASE}/files/sign",
                headers=self._headers(),
                json=payload,
            ) as response,
        ):
            response.raise_for_status()
            data = await response.json()
            return data["data"]

    async def upload(
        self, component: Asset, path: Path, network: str = "public"
    ) -> None:
        """Upload a local file to IPFS via Pinata as `component`. Sets component.cid.

        Files up to ``TUS_THRESHOLD_BYTES`` go via the plain multipart POST;
        larger files use the resumable TUS endpoint (chunked, no resume yet).

        Args:
            component: Asset whose keyvalues describe the file
            path: The local file to upload
            network: "public" or "private"
        """
        path = Path(path)
        kv = _stamp_owner(component.to_keyvalues())
        if path.stat().st_size > TUS_THRESHOLD_BYTES:
            await self._upload_tus(component, path, kv, network)
        else:
            await self._upload_plain(component, path, kv, network)

    async def _upload_plain(
        self, component: Asset, path: Path, kv: dict[str, str], network: str
    ) -> None:
        """Plain multipart POST upload (≤ TUS_THRESHOLD_BYTES)."""
        url = f"{self.UPLOAD_BASE}/files"

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", open(path, "rb"), filename=path.name)
            data.add_field("name", path.name)
            data.add_field("network", network)
            if kv:
                data.add_field("keyvalues", json.dumps(kv))

            async with session.post(
                url, headers=self._headers(), data=data
            ) as response:
                response.raise_for_status()
                result = await response.json()
                data_obj = result.get("data", result)
                component.cid = data_obj["cid"]

    async def _upload_tus(
        self, component: Asset, path: Path, kv: dict[str, str], network: str
    ) -> None:
        """Resumable TUS upload for large files (chunked, no resume yet).

        Creates an upload, streams the file in ``TUS_CHUNK_BYTES`` chunks via
        ``PATCH``, and reads the resulting CID from the ``Upload-Cid`` header
        on the completing response.
        """
        metadata = _tus_metadata(path.name, network, kv)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.UPLOAD_BASE}/files",
                headers={
                    **self._headers(),
                    "Tus-Resumable": "1.0.0",
                    "Content-Type": "application/offset+octet-stream",
                    "Upload-Length": str(path.stat().st_size),
                    "Upload-Metadata": metadata,
                },
            ) as response:
                response.raise_for_status()
                location = response.headers["Location"]

            offset = 0
            cid = None
            async with aiofiles.open(path, "rb") as f:
                while True:
                    chunk = await f.read(TUS_CHUNK_BYTES)
                    if not chunk:
                        break
                    async with session.patch(
                        location,
                        headers={
                            **self._headers(),
                            "Tus-Resumable": "1.0.0",
                            "Upload-Offset": str(offset),
                            "Content-Type": "application/offset+octet-stream",
                        },
                        data=chunk,
                    ) as response:
                        response.raise_for_status()
                        offset = int(response.headers["Upload-Offset"])
                        cid = response.headers.get("Upload-Cid", cid)

        if not cid:
            raise ValueError("TUS upload completed but returned no Upload-Cid")
        component.cid = cid

    async def query(
        self, keyvalues: dict[str, str], network: str = "public"
    ) -> list[dict]:
        """Query one Pinata network's files by keyvalue metadata.

        Args:
            keyvalues: Metadata key-value pairs to filter by
            network: "public" or "private"

        Returns:
            List of matching file records with cid, name, keyvalues, and
            the network they were found on
        """
        seen: dict[str, dict] = {}
        url = f"{self.API_BASE}/files/{network}"
        params: dict = {"pageLimit": 1000, "order": "DESC"}
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
                    seen.setdefault(
                        f["cid"],
                        {
                            "cid": f["cid"],
                            "name": f.get("name", ""),
                            "keyvalues": f.get("keyvalues", {}),
                            "network": network,
                        },
                    )

                next_token = data.get("data", {}).get("next_page_token")
                if not next_token:
                    break
                params["pageToken"] = next_token

        return list(seen.values())

    async def delete(self, component: Asset, network: str = "public") -> None:
        """Delete a file from Pinata by querying for its internal ID first.

        Args:
            component: Asset with cid set
            network: "public" or "private"
        """
        url = f"{self.API_BASE}/files/{network}"
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
                f"{self.API_BASE}/files/{network}/{file_id}",
                headers=self._headers(),
            ) as response:
                response.raise_for_status()

    async def update_metadata(
        self,
        cid: str,
        keyvalues: dict[str, str],
        network: str = "public",
    ) -> dict:
        """Merge keyvalues onto an existing file's metadata (Pinata PUT).

        Pinata's update is a **merge/upsert** (verified empirically): the
        supplied keys are added or overwritten, keys omitted from the patch
        are preserved — there is no key *removal*. The file bytes and CID are
        untouched (the CID is content-addressed; keyvalues live in the
        account index, not the file), so existing ``*_cid`` provenance edges
        pointing at this record stay valid. Looks up the internal file id by
        CID first (Pinata keys updates off the UUID, not the CID), then PUTs.
        ``_owner`` is restamped from ``STARGAZER_OWNER`` (env wins, unset
        passes through) so a re-attributed edit stays consistent with upload.

        Args:
            cid: Content identifier of the file to update
            keyvalues: Metadata patch to merge (partial — only these keys
                change). Reserved ``_*`` keys should be left out; ``_owner``
                is stamped here.
            network: "public" or "private"

        Returns:
            The updated record: ``{cid, name, keyvalues, network}``

        Raises:
            ValueError: when no file exists on ``network`` for ``cid``
        """
        kv = _stamp_owner(dict(keyvalues))
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.API_BASE}/files/{network}",
                headers=self._headers(),
                params={"cid": cid},
            ) as response:
                response.raise_for_status()
                files = (await response.json()).get("data", {}).get("files", [])
            if not files:
                raise ValueError(f"No file on {network} network for cid {cid}")
            file_id = files[0]["id"]

            async with session.put(
                f"{self.API_BASE}/files/{network}/{file_id}",
                headers=self._headers(),
                json={"keyvalues": kv},
            ) as response:
                response.raise_for_status()
                data = (await response.json()).get("data", {})

        return {
            "cid": data.get("cid", cid),
            "name": data.get("name", ""),
            "keyvalues": data.get("keyvalues", kv),
            "network": network,
        }
