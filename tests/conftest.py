"""Pytest configuration for Flyte v2 tests."""

import pytest
import flyte


@pytest.fixture(scope="session", autouse=True)
def init_flyte_context():
    """Initialize Flyte context for all tests.

    This fixture ensures that Flyte is properly initialized, which is required
    for task execution and IO operations.

    Note: Tests provide explicit remote_destination to Dir.from_local() to avoid
    needing raw_data path context setup.
    """
    # Initialize Flyte from config
    flyte.init_from_config()
    yield
