"""Conftest for types tests — forces LocalStorageClient in all type modules."""

import pytest
import stargazer.types.alignment as _alignment_mod
import stargazer.types.reference as _reference_mod
import stargazer.types.reads as _reads_mod
import stargazer.types.variants as _variants_mod

from pathlib import Path

# Expose FIXTURES_DIR so test files can import it
from stargazer.utils.local_storage import LocalStorageClient
from stargazer.utils.storage import default_client as _real_client

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(autouse=True)
def setup_local_mode(request, tmp_path):
    """Override parent fixture: patch type modules with a fresh LocalStorageClient."""
    if request.node.get_closest_marker("pinata"):
        yield
        return

    test_local_dir = tmp_path / "stargazer_types_test"
    test_local_dir.mkdir(parents=True, exist_ok=True)

    # Fresh isolated LocalStorageClient for this test
    local_client = LocalStorageClient(local_dir=test_local_dir)

    # Patch all type modules (their update/fetch methods use module-level default_client)
    orig_aln = _alignment_mod.default_client
    orig_ref = _reference_mod.default_client
    orig_reads = _reads_mod.default_client
    orig_var = _variants_mod.default_client

    _alignment_mod.default_client = local_client
    _reference_mod.default_client = local_client
    _reads_mod.default_client = local_client
    _variants_mod.default_client = local_client

    # Also align the real client's local_dir so test-file references to
    # `default_client.local_dir` resolve to the same temp directory
    orig_real_local_dir = _real_client.local_dir
    _real_client.local_dir = test_local_dir

    yield

    # Restore
    _alignment_mod.default_client = orig_aln
    _reference_mod.default_client = orig_ref
    _reads_mod.default_client = orig_reads
    _variants_mod.default_client = orig_var
    _real_client.local_dir = orig_real_local_dir
