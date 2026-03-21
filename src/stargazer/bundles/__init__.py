"""
### Resource bundle loader for Stargazer.

Discovers YAML bundle definitions from this package directory and provides
hydration into local storage. Bundles are curated sets of files identified
by CID with associated keyvalue metadata.

**With JWT (remote mode):** Files are already registered in Pinata with a
``bundle`` keyvalue. The tool downloads bytes by CID via the standard path.
No TinyDB writes occur.

**Without JWT (local mode):** The manifest's keyvalues are seeded into TinyDB
so ``assemble()`` can find them. Bytes are fetched from the public IPFS gateway.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from tinydb import Query

logger = logging.getLogger(__name__)

_BUNDLE_DIR = Path(__file__).parent


def list_bundles() -> list[dict]:
    """Return metadata for all discovered bundle YAML files.

    Returns:
        List of dicts with 'name', 'description', and 'file_count' keys.
    """
    bundles = []
    for p in sorted(_BUNDLE_DIR.glob("*.yaml")):
        with p.open() as f:
            data = yaml.safe_load(f)
        bundles.append(
            {
                "name": data["name"],
                "description": data.get("description", ""),
                "file_count": len(data.get("files", [])),
            }
        )
    return bundles


async def fetch_bundle(bundle_name: str) -> list[dict]:
    """Fetch a resource bundle by downloading files by CID.

    In remote mode (JWT set), files are assumed to be registered in Pinata
    with a ``bundle`` keyvalue. Only bytes are downloaded — no local metadata
    writes.

    In local mode (no JWT), the manifest's keyvalues are seeded into TinyDB
    so ``assemble()`` can discover them. Bytes are fetched from the public
    IPFS gateway.

    Args:
        bundle_name: Name of the bundle (matches the 'name' field in a YAML file).

    Returns:
        List of dicts with 'cid', 'keyvalues', and 'path' for each fetched file.

    Raises:
        ValueError: If the bundle name is not found.
    """
    from stargazer.types.asset import Asset
    from stargazer.utils.local_storage import default_client

    manifest = _load_manifest(bundle_name)
    is_local = default_client.remote is None
    results = []

    for entry in manifest["files"]:
        cid = entry["cid"]
        manifest_kv = entry["keyvalues"]

        name = entry.get("name", "")

        # Local mode: seed TinyDB so assemble() can find these assets
        if is_local:
            _upsert_local(cid, manifest_kv, name, default_client)

        # Download bytes via standard path (cache → remote → public gateway)
        comp = Asset(cid=cid)
        cached = await default_client.download(comp, name=name or None)

        results.append(
            {
                "cid": cid,
                "name": name,
                "keyvalues": manifest_kv,
                "path": str(comp.path),
                "cached": cached,
            }
        )

    return results


def _load_manifest(bundle_name: str) -> dict:
    """Load a bundle YAML file by name.

    Args:
        bundle_name: The 'name' field to match in YAML files.

    Returns:
        Parsed YAML dict.

    Raises:
        ValueError: If no matching bundle is found.
    """
    for p in _BUNDLE_DIR.glob("*.yaml"):
        with p.open() as f:
            data = yaml.safe_load(f)
        if data.get("name") == bundle_name:
            return data

    available = [_read_name(p) for p in _BUNDLE_DIR.glob("*.yaml")]
    raise ValueError(f"Bundle {bundle_name!r} not found. Available: {available}")


def _read_name(path: Path) -> str:
    """Read just the name field from a bundle YAML."""
    with path.open() as f:
        data = yaml.safe_load(f)
    return data.get("name", path.stem)


def _upsert_local(cid: str, keyvalues: dict[str, str], name: str, client) -> None:
    """Upsert a CID + keyvalues record into TinyDB.

    Only called in local mode (no JWT) to seed metadata for assemble().

    Args:
        cid: Content identifier.
        keyvalues: Metadata to store.
        name: Human-readable filename for the asset.
        client: LocalStorageClient instance.
    """
    now = datetime.now(timezone.utc)
    File = Query()
    client.db.upsert(
        {
            "cid": cid,
            "name": name,
            "keyvalues": keyvalues,
            "created_at": now.isoformat(),
            "rel_path": name,
        },
        File.cid == cid,
    )
