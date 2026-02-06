"""Pytest configuration for Flyte v2 tests."""

import sys
from pathlib import Path

import pytest
import flyte

from stargazer.utils.pinata import default_client

# Add tests directory to Python path for config imports
sys.path.insert(0, str(Path(__file__).parent))

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DB = FIXTURES_DIR / "stargazer_local.json"


@pytest.fixture(scope="session", autouse=True)
def init_flyte_context():
    """Initialize Flyte context for all tests.

    This fixture ensures that Flyte is properly initialized, which is required
    for task execution.
    """
    # Initialize Flyte from config
    flyte.init_from_config()
    yield


@pytest.fixture(autouse=True)
def setup_local_only_mode(tmp_path):
    """Configure tests to run in local-only mode with isolated TinyDB.

    This fixture ensures all tests run without network requirements by:
    - Setting PinataClient to local-only mode
    - Using an isolated local directory for each test
    - Using an isolated TinyDB database for metadata

    Args:
        tmp_path: pytest's built-in temporary directory fixture

    Yields:
        None
    """
    # Store original settings
    original_local_only = default_client.local_only
    original_local_dir = default_client.local_dir
    original_db = default_client._db

    # Use temp directory for test isolation
    test_local_dir = tmp_path / "stargazer_test"
    test_local_dir.mkdir(parents=True, exist_ok=True)

    # Configure local-only mode
    default_client.local_only = True
    default_client.local_dir = test_local_dir
    default_client.local_db_path = test_local_dir / "stargazer_local.json"
    default_client._db = None  # Reset to trigger lazy init with new path

    yield

    # Restore original settings
    default_client.local_only = original_local_only
    default_client.local_dir = original_local_dir
    default_client._db = original_db


@pytest.fixture
def fixtures_db(tmp_path):
    """Two-phase fixture: query inputs from fixtures, run tasks in clean tmp.

    Phase 1 (query): Points default_client at the fixtures directory and its
    pre-built TinyDB so tests can use query_files() / hydrate() to resolve
    inputs into proper types. Hydration sets local_path on every IpFile to
    the real fixture file.

    Phase 2 (checkout): Call the returned function to switch default_client
    to an empty tmp dir. Task outputs land there with no pre-existing results.
    Since hydrated IpFiles already have local_path set, calling fetch() on
    them is a no-op — inputs are read directly from fixtures.

    Usage:
        async def test_something(fixtures_db):
            refs = await hydrate({"type": "reference", "build": "GRCh38"})
            alignments = await hydrate({"type": "alignment", ...})
            fixtures_db()                          # switch to clean tmp
            await refs[0].fetch()                  # no-op, local_path set
            await alignments[0].fetch()            # no-op, local_path set
            result = await some_task(alignments[0], ref=refs[0])
    """
    # Phase 1: point at fixtures for querying
    default_client.local_dir = FIXTURES_DIR
    default_client.local_db_path = FIXTURES_DB
    default_client._db = None

    def checkout():
        """Switch default_client to an empty tmp dir for task outputs."""
        work_dir = tmp_path / "stargazer_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        default_client.local_dir = work_dir
        default_client.local_db_path = work_dir / "stargazer_local.json"
        default_client._db = None

    return checkout
