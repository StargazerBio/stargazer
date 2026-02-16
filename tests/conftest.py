"""Pytest configuration for Flyte v2 tests."""

import os
import sys
from pathlib import Path

# Force local storage mode for tests before any stargazer imports
os.environ.pop("PINATA_JWT", None)
os.environ["STARGAZER_MODE"] = "local"

import pytest
import flyte

from stargazer.utils.storage import default_client

# Add tests directory to Python path for config imports
sys.path.insert(0, str(Path(__file__).parent))

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DB = FIXTURES_DIR / "stargazer_local.json"


@pytest.fixture(scope="session", autouse=True)
def init_flyte_context():
    """Initialize Flyte context for all tests."""
    flyte.init_from_config()
    yield


@pytest.fixture(autouse=True)
def setup_local_mode(tmp_path):
    """Configure tests to run in local mode with isolated storage."""
    # Store original settings
    original_local_dir = default_client.local_dir
    original_db = default_client._db
    original_db_path = default_client.local_db_path

    # Use temp directory for test isolation
    test_local_dir = tmp_path / "stargazer_test"
    test_local_dir.mkdir(parents=True, exist_ok=True)

    # Configure local directory
    default_client.local_dir = test_local_dir
    default_client.local_db_path = test_local_dir / "stargazer_local.json"
    default_client._db = None

    yield

    # Restore original settings
    default_client.local_dir = original_local_dir
    default_client._db = original_db
    default_client.local_db_path = original_db_path


@pytest.fixture
def fixtures_db(tmp_path):
    """Two-phase fixture: query inputs from fixtures, run tasks in clean tmp."""
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
