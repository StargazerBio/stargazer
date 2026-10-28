"""Pytest configuration for Flyte v2 tests.

Every top-level directory under tests/ belongs to exactly one tier, and its
tests carry that tier's marker (`TIERS`). A bare run selects the unit tier
(`addopts` in pyproject.toml); `-m tasks`, `-m devbox`, `-m pinata`,
`-m postgres` or `-m dsql` selects another. The write-tests skill's Test
Tiers has where each one runs.

PINATA_JWT is stripped before any stargazer imports, so storage runs without
the public tier; the pinata tier's conftest sets it back for its own tests.

Every test runs against its own empty store, index and cache under tmp_path
(`isolated_storage`, autouse), so nothing reads or writes ~/.stargazer.
`fixtures_db` swaps in a store seeded once per session with the fixture files.
"""

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

# Strip PINATA_JWT before importing stargazer so no client gets a public tier.
os.environ.pop("PINATA_JWT", None)

import pytest

import stargazer.utils.storage as _storage_mod
from stargazer.config import init_flyte
from stargazer.utils.cid import compute_cid
from stargazer.utils.index import SqliteIndex
from stargazer.utils.storage import StorageClient

# Add tests directory to Python path for config and fixture imports
sys.path.insert(0, str(Path(__file__).parent))

from fixtures.seed import seed

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GENERAL_FIXTURES_DIR = FIXTURES_DIR / "general"
GATK_FIXTURES_DIR = FIXTURES_DIR / "gatk"
SCRNA_FIXTURES_DIR = FIXTURES_DIR / "scrna"
SECRETS_DIR = Path(__file__).parent / ".secrets"
TESTS_DIR = Path(__file__).parent

# The tier each top-level directory under tests/ belongs to. Its name is the
# marker that selects it.
TIERS = {
    "assets": "unit",
    "notebooks": "unit",
    "unit": "unit",
    "utils": "unit",
    "tasks": "tasks",
    "devbox": "devbox",
    "pinata": "pinata",
    "postgres": "postgres",
    "dsql": "dsql",
}


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    """Mark every test with its directory's tier, before `-m` selects by it."""
    for item in items:
        top = item.path.relative_to(TESTS_DIR).parts[0]
        if top not in TIERS:
            raise pytest.UsageError(
                f"tests/{top} isn't in a tier: add it to TIERS in tests/conftest.py"
            )
        item.add_marker(TIERS[top])


def make_client(
    root: Path, cache: str = "local", public=None, gateway: str | None = None
) -> StorageClient:
    """A storage client whose store, index and cache (`cache`) live under `root`."""
    return StorageClient(
        local_dir=root / cache,
        store_root=str(root / "store"),
        index=SqliteIndex(root / "index.db"),
        public=public,
        gateway=gateway,
    )


class FakePublicTier:
    """Stands in for Pinata's public network, logging every query and upload.

    Records live in memory. `add` also serves a record's bytes from a local
    `gateway` directory at `<gateway>/ipfs/<cid>`, so a client built with
    that gateway downloads them. `upload` assigns `cid`, or the CID Pinata
    would.
    """

    def __init__(self, gateway: Path | None = None, cid: str = ""):
        """An empty tier; `cid` forces the CID every upload gets."""
        self.gateway = gateway
        self.cid = cid
        self.records: list[dict] = []
        self.queries: list[dict] = []
        self.uploads: list[dict] = []

    def add(self, name: str, data: bytes, **keyvalues: str) -> None:
        """Publish `data` as `name`, served at <gateway>/ipfs/<cid>."""
        staged = self.gateway / "staging" / name
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(data)
        cid = compute_cid(staged)
        (self.gateway / "ipfs").mkdir(exist_ok=True)
        staged.rename(self.gateway / "ipfs" / cid)
        self.records.append({"cid": cid, "name": name, "keyvalues": keyvalues})

    async def query(self, keyvalues: dict) -> list[dict]:
        """The records matching every keyvalue."""
        self.queries.append(dict(keyvalues))
        return [
            r
            for r in self.records
            if all(r["keyvalues"].get(k) == v for k, v in keyvalues.items())
        ]

    async def get(self, cid: str) -> dict | None:
        """The record for `cid`, or None."""
        return next((r for r in self.records if r["cid"] == cid), None)

    async def upload(self, component, path: Path) -> None:
        """Log the upload and set `component.cid`."""
        path = Path(path)
        self.uploads.append(
            {
                "bytes": path.read_bytes(),
                "name": path.name,
                "keyvalues": component.to_keyvalues(),
            }
        )
        component.cid = self.cid or compute_cid(path)


@pytest.fixture(scope="session", autouse=True)
def init_flyte_context():
    """Initialize Flyte context for all tests."""
    init_flyte()
    yield


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Point the default storage client at an empty per-test store, index and cache."""
    monkeypatch.delenv("STARGAZER_OWNER", raising=False)
    client = make_client(tmp_path / "storage")
    monkeypatch.setattr(_storage_mod, "default_client", client)
    return client


@pytest.fixture(scope="session")
def seeded_client(tmp_path_factory) -> StorageClient:
    """A store and index holding every fixture file, built once per session."""
    client = make_client(tmp_path_factory.mktemp("fixtures_store"))
    asyncio.run(seed(client))
    return client


@pytest.fixture
def fixtures_db(seeded_client, tmp_path, monkeypatch):
    """Two-phase fixture: query inputs from the seeded store, run tasks in a clean one.

    Phase 1 (before calling checkout): the default client is the seeded
    fixtures store, so tests can query it and build assets with real CIDs.

    Phase 2 (after calling checkout()): the default client switches to an
    empty per-test store, so task outputs are isolated per test.
    """
    monkeypatch.setattr(_storage_mod, "default_client", seeded_client)

    def checkout():
        """Switch the default client to an empty store for task outputs."""
        monkeypatch.setattr(
            _storage_mod, "default_client", make_client(tmp_path / "work")
        )

    return checkout


def load_proxy():
    """Load the notebook proxy (`runtime/proxy.py`), which isn't in the package.

    Loaded as `sg_proxy`, the name it has in the image.
    """
    spec = importlib.util.spec_from_file_location(
        "sg_proxy", TESTS_DIR.parent / "runtime" / "proxy.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["sg_proxy"] = module
    spec.loader.exec_module(module)
    return module
