"""Unit test configuration — override the broken autouse fixture from parent conftest."""

import pytest

from stargazer.utils.storage import default_client


@pytest.fixture(autouse=True)
def setup_local_mode(request, tmp_path):
    """Configure tests to run in local mode with isolated storage."""
    if request.node.get_closest_marker("pinata"):
        yield
        return

    from stargazer.utils.local_storage import LocalStorageClient

    if not isinstance(default_client, LocalStorageClient):
        yield
        return

    original_local_dir = default_client.local_dir
    original_db = default_client._db
    original_db_path = default_client.local_db_path

    test_local_dir = tmp_path / "stargazer_test"
    test_local_dir.mkdir(parents=True, exist_ok=True)

    default_client.local_dir = test_local_dir
    default_client.local_db_path = test_local_dir / "stargazer_local.json"
    default_client._db = None

    yield

    default_client.local_dir = original_local_dir
    default_client._db = original_db
    default_client.local_db_path = original_db_path
