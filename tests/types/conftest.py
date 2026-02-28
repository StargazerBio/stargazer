"""Conftest for types tests — forces LocalStorageClient for all storage operations."""

import pytest
import stargazer.utils.storage as _storage_mod

from pathlib import Path

from stargazer.utils.local_storage import LocalStorageClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(autouse=True)
def setup_local_mode(request, tmp_path):
    """Patch storage.default_client with a fresh LocalStorageClient."""
    if request.node.get_closest_marker("pinata"):
        yield
        return

    test_local_dir = tmp_path / "stargazer_types_test"
    test_local_dir.mkdir(parents=True, exist_ok=True)

    local_client = LocalStorageClient(local_dir=test_local_dir)

    orig_client = _storage_mod.default_client
    _storage_mod.default_client = local_client

    yield

    _storage_mod.default_client = orig_client
