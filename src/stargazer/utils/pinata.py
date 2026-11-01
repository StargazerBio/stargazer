"""
### Pinata API v3 client for IPFS file storage.

Provides async interface for authenticated Pinata operations:
- Uploading files with keyvalue metadata
- Querying files by keyvalue pairs
- Updating metadata and deleting files
- Resumable (TUS) uploads, chunk by chunk, for a caller relaying a file

Stargazer uses Pinata's public network only: shared data lives there,
readable by everyone and attributed by `_owner`. Every public write needs an
`_owner`, and reads skip a file without one. Private data lives in each
user's own store (`stargazer.utils.storage`), never on Pinata's private
network. `_owner` records who made a record and decides which public
companions a fetch takes; it grants nothing, since anyone with the key can
edit or delete any public record.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import base64
import json
import os
from pathlib import Path

import aiofiles
import aiohttp

from stargazer.assets.asset import Asset

# Pinata's plain multipart POST is capped at 100MB; larger files must use the
# resumable TUS endpoint. upload() switches paths at this threshold. Chunks
# must stay under Pinata's 50MB TUS limit; per-file ceiling is 10 GiB.
TUS_THRESHOLD_BYTES = 100 * 1024**2
TUS_CHUNK_BYTES = 48 * 1024**2

# Pinata refuses a new file with more keyvalues than this, `_owner` included
# (measured 2026-10-13: 9 stored, 10 rejected, on plain and signed uploads).
# A metadata update has no such limit, so only uploads are checked.
MAX_KEYVALUES = 9

# Pinata refuses a key or value longer than this on a new file (measured
# 2026-10-15: 250 stored, 251 refused). An update allows 255 and answers 256
# with a bare "malformed" 400; both are held to 250, so whatever can be
# edited onto a record could also be uploaded with it.
MAX_KEYVALUE_CHARS = 250

# The only Pinata network Stargazer uses. Private data lives in each user's own
# store; with the org's shared key, Pinata's private network would hide nothing.
NETWORK = "public"


def _tus_metadata(filename: str, keyvalues: dict[str, str]) -> str:
    """Encode TUS ``Upload-Metadata``: comma-joined ``key b64(value)`` pairs.

    Pinata reads ``filename``, ``network``, and ``keyvalues`` (stringified
    JSON) from this header on the creation POST.
    """
    fields = {
        "filename": filename,
        "network": NETWORK,
        "keyvalues": json.dumps(keyvalues),
    }
    return ",".join(
        f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in fields.items()
    )


def _record(f: dict) -> dict:
    """A Pinata file listing entry as a public record."""
    return {
        "cid": f["cid"],
        "name": f.get("name", ""),
        "keyvalues": f.get("keyvalues", {}),
        "network": NETWORK,
    }


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


def _check_owner(kv: dict[str, str]) -> None:
    """Raise unless `kv` carries an `_owner`.

    Every public record names who published it: companions follow their
    parent's `_owner`, and only the owner may edit a record from the page.
    Reads skip a record without one, since anyone with the key can upload
    straight to Pinata.
    """
    if not kv.get("_owner"):
        raise ValueError(
            "A public record needs an owner, and these keyvalues have no "
            "`_owner`: set STARGAZER_OWNER"
        )


def _owned(f: dict) -> bool:
    """Whether a Pinata file listing entry names its owner."""
    return bool(f.get("keyvalues", {}).get("_owner"))


def _check_keyvalue_count(kv: dict[str, str]) -> None:
    """Raise unless `kv` fits on a new Pinata file (``MAX_KEYVALUES`` keys).

    Checked before anything is sent: a plain upload past the cap would ship
    the whole file to get a 400.
    """
    if len(kv) > MAX_KEYVALUES:
        raise ValueError(
            f"An upload can carry at most {MAX_KEYVALUES} metadata fields, "
            f"counting the asset type and owner; this one has {len(kv)}."
        )


def _check_keyvalue_lengths(kv: dict[str, str]) -> None:
    """Raise unless every key and value is at most ``MAX_KEYVALUE_CHARS`` long.

    Checked before anything is sent, on uploads and updates alike. A list
    stored as one value (``source_samples``) is what runs long.
    """
    for key, value in kv.items():
        longest = max(len(key), len(value))
        if longest > MAX_KEYVALUE_CHARS:
            raise ValueError(
                "A metadata field's name and value can each be at most "
                f"{MAX_KEYVALUE_CHARS} characters; {key[:40]!r} has {longest}."
            )


def _check_new_file(kv: dict[str, str]) -> None:
    """Raise unless `kv` can go on a new public file: owned and within limits."""
    _check_keyvalue_count(kv)
    _check_keyvalue_lengths(kv)
    _check_owner(kv)


class PinataClient:
    """Async client for Pinata API v3, on Pinata's public network (`NETWORK`).

    Uploads (plain or TUS), keyvalue queries, metadata updates and deletes.
    A pure remote transport: caching and gateway downloads are the storage
    client's job (`stargazer.utils.storage`).

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

    async def _files(self, session: aiohttp.ClientSession, cid: str) -> list[dict]:
        """The public network's file listings for `cid`, owned or not."""
        async with session.get(
            f"{self.API_BASE}/files/{NETWORK}",
            headers=self._headers(),
            params={"cid": cid},
        ) as response:
            response.raise_for_status()
            return (await response.json()).get("data", {}).get("files", [])

    async def tus_create(
        self, filename: str, keyvalues: dict[str, str], length: int
    ) -> str:
        """Start a resumable TUS upload of ``length`` bytes on the public network.

        Args:
            filename: Name the uploaded file will carry
            keyvalues: The file's metadata, `_owner` included (checked here,
                not stamped)
            length: The whole file's size in bytes

        Returns:
            The upload's URL, which each chunk is sent to (``tus_patch``)

        Raises:
            ValueError: when ``keyvalues`` has no ``_owner``, more than
                ``MAX_KEYVALUES`` keys or one longer than
                ``MAX_KEYVALUE_CHARS``, before any request is made
        """
        _check_new_file(keyvalues)
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.UPLOAD_BASE}/files",
                headers={
                    **self._headers(),
                    "Tus-Resumable": "1.0.0",
                    "Content-Type": "application/offset+octet-stream",
                    "Upload-Length": str(length),
                    "Upload-Metadata": _tus_metadata(filename, keyvalues),
                },
            ) as response,
        ):
            response.raise_for_status()
            return response.headers["Location"]

    async def tus_patch(self, location: str, offset: int, chunk: bytes) -> str | None:
        """Send one chunk of a TUS upload, at most ``TUS_CHUNK_BYTES``.

        Args:
            location: The upload's URL, from ``tus_create``
            offset: Where in the file ``chunk`` starts
            chunk: The bytes

        Returns:
            The file's CID once the chunk completing it lands, else None
        """
        async with (
            aiohttp.ClientSession() as session,
            session.patch(
                location,
                headers={
                    **self._headers(),
                    "Tus-Resumable": "1.0.0",
                    "Upload-Offset": str(offset),
                    "Content-Type": "application/offset+octet-stream",
                },
                data=chunk,
            ) as response,
        ):
            response.raise_for_status()
            return response.headers.get("Upload-Cid")

    async def upload(self, component: Asset, path: Path) -> None:
        """Upload a local file to IPFS via Pinata as `component`. Sets component.cid.

        Files up to ``TUS_THRESHOLD_BYTES`` go via the plain multipart POST;
        larger files use the resumable TUS endpoint (chunked, no resume yet).

        Args:
            component: Asset whose keyvalues describe the file
            path: The local file to upload

        Raises:
            ValueError: when the stamped keyvalues have no ``_owner``, more
                than ``MAX_KEYVALUES`` keys or one longer than
                ``MAX_KEYVALUE_CHARS``, before any bytes are sent
        """
        path = Path(path)
        kv = _stamp_owner(component.to_keyvalues())
        if path.stat().st_size > TUS_THRESHOLD_BYTES:
            await self._upload_tus(component, path, kv)
        else:
            _check_new_file(kv)
            await self._upload_plain(component, path, kv)

    async def _upload_plain(
        self, component: Asset, path: Path, kv: dict[str, str]
    ) -> None:
        """Plain multipart POST upload (≤ TUS_THRESHOLD_BYTES)."""
        url = f"{self.UPLOAD_BASE}/files"

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", open(path, "rb"), filename=path.name)
            data.add_field("name", path.name)
            data.add_field("network", NETWORK)
            data.add_field("keyvalues", json.dumps(kv))

            async with session.post(
                url, headers=self._headers(), data=data
            ) as response:
                response.raise_for_status()
                result = await response.json()
                data_obj = result.get("data", result)
                component.cid = data_obj["cid"]

    async def _upload_tus(
        self, component: Asset, path: Path, kv: dict[str, str]
    ) -> None:
        """Resumable TUS upload for large files (chunked, no resume yet).

        Sends the file in ``TUS_CHUNK_BYTES`` chunks and takes the CID Pinata
        answers the last one with.
        """
        location = await self.tus_create(path.name, kv, path.stat().st_size)
        offset = 0
        cid = None
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(TUS_CHUNK_BYTES):
                cid = await self.tus_patch(location, offset, chunk)
                offset += len(chunk)
        if not cid:
            raise ValueError("TUS upload completed but returned no Upload-Cid")
        component.cid = cid

    async def query(self, keyvalues: dict[str, str]) -> list[dict]:
        """Query the public network's files by keyvalue metadata.

        Files with no `_owner` are left out.

        Args:
            keyvalues: Metadata key-value pairs to filter by

        Returns:
            List of matching file records with cid, name, keyvalues, and
            network
        """
        seen: dict[str, dict] = {}
        url = f"{self.API_BASE}/files/{NETWORK}"
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
                    if _owned(f):
                        seen.setdefault(f["cid"], _record(f))

                next_token = data.get("data", {}).get("next_page_token")
                if not next_token:
                    break
                params["pageToken"] = next_token

        return list(seen.values())

    async def get(self, cid: str) -> dict | None:
        """The public network's owned record for `cid`, or None if it has none.

        Returns:
            The record (cid, name, keyvalues, network), or None
        """
        async with aiohttp.ClientSession() as session:
            owned = [f for f in await self._files(session, cid) if _owned(f)]
        return _record(owned[0]) if owned else None

    async def delete(self, component: Asset) -> None:
        """Delete a file from Pinata by querying for its internal ID first.

        Args:
            component: Asset with cid set
        """
        async with aiohttp.ClientSession() as session:
            files = await self._files(session, component.cid)
            if not files:
                return
            async with session.delete(
                f"{self.API_BASE}/files/{NETWORK}/{files[0]['id']}",
                headers=self._headers(),
            ) as response:
                response.raise_for_status()

    async def update_metadata(self, cid: str, keyvalues: dict[str, str]) -> dict:
        """Merge keyvalues onto an existing file's metadata (Pinata PUT).

        Pinata's update is a **merge/upsert** (verified empirically): the
        supplied keys are added or overwritten, keys omitted from the patch
        are preserved — there is no key *removal*. The file bytes and CID are
        untouched (the CID is content-addressed; keyvalues live in the
        account index, not the file), so existing ``*_cid`` provenance edges
        pointing at this record stay valid. Pinata keys updates off the
        file's id, so the id is looked up by CID first.

        Args:
            cid: Content identifier of the file to update
            keyvalues: Metadata patch to merge (partial — only these keys
                change), ``_owner`` included: the caller names the owner

        Returns:
            The updated record: ``{cid, name, keyvalues, network}``

        Raises:
            ValueError: when the patch has no ``_owner`` or a key or value
                longer than ``MAX_KEYVALUE_CHARS``, before any request is
                made, or when no public file exists for ``cid``
        """
        kv = dict(keyvalues)
        _check_keyvalue_lengths(kv)
        _check_owner(kv)
        async with aiohttp.ClientSession() as session:
            files = await self._files(session, cid)
            if not files:
                raise ValueError(f"No public file for cid {cid}")
            async with session.put(
                f"{self.API_BASE}/files/{NETWORK}/{files[0]['id']}",
                headers=self._headers(),
                json={"keyvalues": kv},
            ) as response:
                response.raise_for_status()
                data = (await response.json()).get("data", {})
        return _record({"cid": cid, "keyvalues": kv, **data})
