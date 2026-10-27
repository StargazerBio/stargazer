"""
### Public notebooks: workspace notebooks published to the public tier.

A workspace notebook is a plain file in its owner's workspace store until
they publish it from its dashboard tile. Publishing uploads the file to
Pinata's public network as a `Notebook` asset, through the same Pinata client
and TUS upload the asset browser uses (`app.assets`), stamped with the
owner's subject as `_owner`. A user has at most one public record per
notebook: publishing again deletes their earlier records with the same
`slug`, and unpublishing deletes them all. Another user's records are never
touched, since every lookup is by the user's own `_owner`.

Pinata stores identical bytes once per account and keeps the first upload's
keyvalues, so a file that's already public under another record (someone
else's, or another of the user's notebooks) can't be published again; the
upload comes back as that record, and publishing refuses it
(`AlreadyPublic`).

The dashboard lists every public notebook in its own section, read from the
asset browser's cached public listing, and copies one into a workspace by
reading its bytes from the gateway.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os

import aiohttp

from app import assets
from stargazer.assets import Notebook
from stargazer.assets.asset import Asset
from stargazer.utils.pinata import TUS_CHUNK_BYTES

NOTEBOOK_KEY = Notebook._asset_key


class AlreadyPublic(Exception):
    """The notebook's bytes are already public under another record."""


def _is_notebook(record: dict) -> bool:
    """Whether a public record is a published notebook."""
    return record["keyvalues"].get("asset") == NOTEBOOK_KEY


async def public_notebooks() -> list[dict]:
    """Every published notebook's public record, from the cached listing."""
    return [r for r in await assets._public_records() if _is_notebook(r)]


async def _own_records(subject: str, slug: str) -> list[dict]:
    """`subject`'s public notebook records for `slug`, read fresh from Pinata."""
    records = await assets._pinata().query(
        {"asset": NOTEBOOK_KEY, "slug": slug, "_owner": subject}
    )
    return [
        r
        for r in records
        if r["keyvalues"].get("_owner") == subject
        and r["keyvalues"].get("slug") == slug
    ]


async def publish(
    subject: str, slug: str, title: str, description: str, source: str
) -> str:
    """Publish workspace notebook `slug` as `subject`'s, replacing any earlier copy.

    Returns the public record's CID.

    Raises:
        ValueError: when the keyvalues are past Pinata's limits (a long
            `description`), before anything is sent
        AlreadyPublic: when the bytes are already public under another
            record; nothing is deleted
    """
    keyvalues = {
        **Notebook(title=title, description=description, slug=slug).to_keyvalues(),
        "_owner": subject,
    }
    data = source.encode()
    if not data:
        raise ValueError("The notebook is empty.")
    pinata = assets._pinata()
    url = await pinata.tus_create(f"{slug}.py", keyvalues, len(data))
    cid = None
    for offset in range(0, len(data), TUS_CHUNK_BYTES):
        cid = await pinata.tus_patch(
            url, offset, data[offset : offset + TUS_CHUNK_BYTES]
        )
    stored = await pinata.get(cid)
    if stored is not None and (
        stored["keyvalues"].get("_owner") != subject
        or stored["keyvalues"].get("slug") != slug
    ):
        raise AlreadyPublic("An identical notebook is already public.")
    for record in await _own_records(subject, slug):
        if record["cid"] != cid:
            await pinata.delete(Asset(cid=record["cid"]))
    assets.forget_public_records()
    return cid


async def unpublish(subject: str, slug: str) -> int:
    """Delete `subject`'s public records for notebook `slug`; return how many."""
    records = await _own_records(subject, slug)
    for record in records:
        await assets._pinata().delete(Asset(cid=record["cid"]))
    assets.forget_public_records()
    return len(records)


async def _read_public(cid: str) -> str:
    """A public file's bytes as text, from the account's gateway."""
    url = f"{os.environ['PINATA_GATEWAY']}/ipfs/{cid}"
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def public_source(cid: str) -> tuple[str, str, str]:
    """A published notebook's `(source, title, description)`.

    Raises:
        LookupError: when `cid` isn't a published notebook
    """
    record = await assets._pinata().get(cid)
    if record is None or not _is_notebook(record):
        raise LookupError(f"no public notebook {cid}")
    kv = record["keyvalues"]
    title = kv.get("title") or kv.get("slug", "")
    return await _read_public(cid), title, kv.get("description", "")
