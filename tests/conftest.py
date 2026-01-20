"""Pytest configuration for Flyte v2 tests."""

import sys
from pathlib import Path

import pytest
import flyte

from stargazer.utils.pinata import default_client

# Add tests directory to Python path for config imports
sys.path.insert(0, str(Path(__file__).parent))


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
