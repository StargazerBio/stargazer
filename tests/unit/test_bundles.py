"""Tests for the resource bundle system."""

import textwrap
from unittest.mock import patch

import pytest

from stargazer.assets.asset import assemble
from stargazer.bundles import _load_manifest, fetch_bundle, list_bundles


@pytest.fixture
def bundle_dir(tmp_path):
    """Create a temp bundle directory with a test YAML."""
    bundle_yaml = tmp_path / "test_demo.yaml"
    bundle_yaml.write_text(
        textwrap.dedent("""\
        name: test_demo
        description: Test bundle for unit tests
        files:
          - cid: bafyTestCID1
            name: s1d1.h5ad
            keyvalues:
              asset: anndata
              bundle: test_demo
              sample_id: s1d1
              stage: raw
              organism: mouse
          - cid: bafyTestCID2
            name: s1d3.h5ad
            keyvalues:
              asset: anndata
              bundle: test_demo
              sample_id: s1d3
              stage: raw
              organism: mouse
        """)
    )
    with patch("stargazer.bundles._BUNDLE_DIR", tmp_path):
        yield tmp_path


@pytest.fixture
def cached_bundle(isolated_storage):
    """Put the bundle's files in the local cache, so fetching needs no network."""
    for cid, name in (("bafyTestCID1", "s1d1.h5ad"), ("bafyTestCID2", "s1d3.h5ad")):
        path = isolated_storage.local_dir / cid / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    return isolated_storage


class TestListBundles:
    """Tests for list_bundles discovery."""

    def test_discovers_yaml_files(self, bundle_dir):
        """list_bundles returns metadata from YAML files."""
        bundles = list_bundles()
        assert len(bundles) == 1
        assert bundles[0]["name"] == "test_demo"
        assert bundles[0]["description"] == "Test bundle for unit tests"
        assert bundles[0]["file_count"] == 2

    def test_empty_directory(self, tmp_path):
        """list_bundles returns empty list when no YAML files exist."""
        with patch("stargazer.bundles._BUNDLE_DIR", tmp_path):
            assert list_bundles() == []


class TestLoadManifest:
    """Tests for manifest loading."""

    def test_loads_by_name(self, bundle_dir):
        """_load_manifest finds the right YAML by name field."""
        manifest = _load_manifest("test_demo")
        assert manifest["name"] == "test_demo"
        assert len(manifest["files"]) == 2

    def test_raises_for_unknown_name(self, bundle_dir):
        """_load_manifest raises ValueError for unknown bundle name."""
        with pytest.raises(ValueError, match="not found"):
            _load_manifest("nonexistent_bundle")


class TestFetchBundle:
    """Tests for fetching a bundle into the cache and the index."""

    @pytest.mark.asyncio
    async def test_registers_files_in_the_index(self, bundle_dir, cached_bundle):
        """Each file's manifest keyvalues land in the index, findable by assemble()."""
        await fetch_bundle("test_demo")

        found = await assemble(asset="anndata", sample_id="s1d1", stage="raw")

        assert [a.cid for a in found] == ["bafyTestCID1"]
        row = await cached_bundle.index.get("bafyTestCID1")
        assert row["uri"] == f"{cached_bundle.gateway}/ipfs/bafyTestCID1"
        assert row["name"] == "s1d1.h5ad"

    @pytest.mark.asyncio
    async def test_reports_local_copies(self, bundle_dir, cached_bundle):
        """Results carry each file's local path and whether it was already cached."""
        results = await fetch_bundle("test_demo")

        assert [r["cid"] for r in results] == ["bafyTestCID1", "bafyTestCID2"]
        assert results[0]["path"] == str(
            cached_bundle.local_dir / "bafyTestCID1" / "s1d1.h5ad"
        )
        assert results[0]["keyvalues"]["bundle"] == "test_demo"
        assert all(r["cached"] for r in results)

    @pytest.mark.asyncio
    async def test_fetching_twice_keeps_one_row_per_file(
        self, bundle_dir, cached_bundle
    ):
        """Re-fetching a bundle doesn't duplicate its rows."""
        await fetch_bundle("test_demo")
        await fetch_bundle("test_demo")

        assert len(await cached_bundle.index.query({"bundle": "test_demo"})) == 2
