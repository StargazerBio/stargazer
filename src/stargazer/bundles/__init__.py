"""
### Resource bundle loader for Stargazer.

Discovers YAML bundle definitions in this package directory and fetches them.
Bundles are curated sets of public files (reference genomes, demo datasets),
each identified by CID with its keyvalue metadata.

Bundle files are public data on Pinata's public network. `fetch_bundle()`
downloads each one from the IPFS gateway into the local cache and registers
it in the user's index (pointing at the gateway), so `assemble()` finds a
fetched bundle whether or not a Pinata key is configured.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

from pathlib import Path

import yaml
from flyte.io import File

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
    """Download a bundle's files and register them in the user's index.

    Args:
        bundle_name: Name of the bundle (matches the 'name' field in a YAML file).

    Returns:
        One dict per file: 'cid', 'name', 'keyvalues', 'path' (the local
        copy) and 'cached' (whether it was already on disk).

    Raises:
        ValueError: If the bundle name is not found.
    """
    import stargazer.utils.storage as _storage
    from stargazer.assets.asset import Asset

    manifest = _load_manifest(bundle_name)
    client = _storage.default_client
    results = []

    for entry in manifest["files"]:
        cid = entry["cid"]
        keyvalues = entry["keyvalues"]
        name = entry.get("name") or cid
        uri = f"{client.gateway}/ipfs/{cid}"

        await client.index.upsert(
            {"cid": cid, "uri": uri, "name": name, "keyvalues": keyvalues}
        )
        cached = (client.local_dir / cid / name).exists()
        local = await client.download(
            Asset(cid=cid, path=File(path=uri, name=name, hash=cid))
        )

        results.append(
            {
                "cid": cid,
                "name": name,
                "keyvalues": keyvalues,
                "path": str(local),
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
