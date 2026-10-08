"""Seed a verify run's store and index with the scrna_demo raw samples.

Copies each bundle file from the verify cache (downloading it once on a miss)
into the run directory and registers it as a local raw AnnData asset, so the
notebook finds it without touching a public gateway.

Usage: uv run python .claude/skills/verify-stargazer/scripts/seed_scrna.py
"""

import asyncio
import os
import shutil
import urllib.request
from pathlib import Path

import yaml

from stargazer.assets.scrna import AnnData

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT / "src" / "stargazer" / "bundles" / "scrna_demo.yaml"
CACHE = Path(
    os.environ.get("VERIFY_CACHE", Path.home() / ".stargazer" / "verify-cache")
)
GATEWAY = os.environ.get("VERIFY_GATEWAY", "https://gateway.pinata.cloud")


def cached(cid: str) -> Path:
    """Return the cached file for a CID, downloading it once on a miss."""
    path = CACHE / cid
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"downloading {cid} from {GATEWAY}")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(f"{GATEWAY}/ipfs/{cid}", tmp)
        tmp.rename(path)
    return path


async def main() -> None:
    """Copy each bundle sample into the run directory and register it."""
    local = Path(os.environ["STARGAZER_LOCAL"])
    defaults = Path.home() / ".stargazer"
    for key, default in (
        ("STARGAZER_LOCAL", defaults / "local"),
        ("STARGAZER_STORE_ROOT", defaults / "store"),
        ("STARGAZER_INDEX_URL", defaults / "index.db"),
    ):
        if Path(os.environ.get(key, str(default))) == default:
            raise SystemExit(f"refusing to seed the user's default store: set {key}")
    local.mkdir(parents=True, exist_ok=True)

    for entry in yaml.safe_load(BUNDLE.read_text())["files"]:
        kv = entry["keyvalues"]
        dest = local / f"{kv['sample_id']}_raw.h5ad"
        shutil.copyfile(cached(entry["cid"]), dest)
        asset = AnnData(sample_id=kv["sample_id"], organism=kv["organism"])
        await asset.update(dest, stage=kv["stage"])
        print(f"seeded {kv['sample_id']} -> {dest.name} ({asset.cid})")


asyncio.run(main())
