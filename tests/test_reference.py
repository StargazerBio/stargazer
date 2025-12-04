"""
Tests for Reference type.

Tests cover:
- Hydrating references from Pinata
"""

import os
import pytest
from stargazer.types import Reference


@pytest.mark.asyncio
async def test_hydrate_single_query():
    """Test hydrate with single scalar values."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Skip - requires reference directories to be uploaded to Pinata
    pytest.skip("Requires reference directories to be uploaded to Pinata")


@pytest.mark.asyncio
async def test_hydrate_multidimensional_query():
    """Test hydrate with list-valued filters (cartesian product)."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Skip - requires reference directories to be uploaded to Pinata
    pytest.skip("Requires reference directories to be uploaded to Pinata")


@pytest.mark.asyncio
async def test_hydrate_no_results():
    """Test that hydrate raises error when no files match."""
    if not os.environ.get("PINATA_JWT"):
        pytest.skip("PINATA_JWT environment variable not set")

    # Test that a query with no matches raises ValueError
    # Using a nonsense build name that definitely doesn't exist
    with pytest.raises(ValueError, match="No files found matching queries"):
        await Reference.hydrate(
            ref_filename="genome.fa",
            build="NonexistentBuild12345",
        )
