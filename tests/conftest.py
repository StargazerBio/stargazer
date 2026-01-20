"""Pytest configuration for Flyte v2 tests."""

import sys
from pathlib import Path

import pytest
import flyte

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
