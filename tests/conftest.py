"""Pytest configuration for Flyte v2 tests.

PINATA_JWT is stripped before any stargazer imports, so storage runs without
the public tier. Tests marked @pytest.mark.pinata get the JWT injected from
tests/.secrets/pinata_jwt at runtime.

Every test runs against its own empty store, index and cache under tmp_path
(`isolated_storage`, autouse), so nothing reads or writes ~/.stargazer.
`fixtures_db` swaps in a store seeded once per session with the fixture files.
"""

import asyncio
import os
import sys
from pathlib import Path

# Strip PINATA_JWT before importing stargazer so no client gets a public tier.
os.environ.pop("PINATA_JWT", None)

import flyte
import pytest

import stargazer.utils.storage as _storage_mod
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


def make_client(root: Path) -> StorageClient:
    """A storage client whose store, index and cache all live under `root`."""
    return StorageClient(
        local_dir=root / "local",
        store_root=str(root / "store"),
        index=SqliteIndex(root / "index.db"),
    )


@pytest.fixture(scope="session", autouse=True)
def init_flyte_context():
    """Initialize Flyte context for all tests."""
    flyte.init_from_config()
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


def pytest_runtest_setup(item):
    """Inject PINATA_JWT for tests marked @pytest.mark.pinata.

    Loads the JWT from tests/.secrets/pinata_jwt. If the file doesn't
    exist, the test is skipped.
    """
    if item.get_closest_marker("pinata"):
        jwt_file = SECRETS_DIR / "pinata_jwt"
        if not jwt_file.exists():
            pytest.skip(f"Pinata JWT not found — put your token in {jwt_file}")
        jwt = jwt_file.read_text().strip()
        if not jwt:
            pytest.skip(f"Pinata JWT file is empty: {jwt_file}")
        os.environ["PINATA_JWT"] = jwt


def pytest_runtest_teardown(item, nextitem):
    """Remove PINATA_JWT after pinata-marked tests."""
    if item.get_closest_marker("pinata"):
        os.environ.pop("PINATA_JWT", None)


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
