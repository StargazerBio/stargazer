"""Pytest configuration and shared fixtures for tests."""

import pytest


@pytest.fixture
def sample_data_dir():
    """Path to test assets directory."""
    import os
    from pathlib import Path

    return Path(__file__).parent / "assets"
