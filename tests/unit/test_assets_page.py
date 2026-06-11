"""Tests for build_asset() and _owner stamping (plan 20, piece 1).

build_asset() is the single validation choke point shared by the MCP
server and the asset-manager page: strict for registered asset keys,
bare-Asset pass-through for unregistered keys, reserved system keys
(underscore-prefixed) rejected everywhere.
"""

from pathlib import Path

import pytest

from stargazer.assets import Asset, build_asset
from stargazer.assets.alignment import Alignment
from stargazer.config import _stargazer_env_vars
from stargazer.utils.pinata import _stamp_owner


class TestBuildAsset:
    def test_missing_asset_key_raises(self):
        with pytest.raises(ValueError, match="must include 'asset'"):
            build_asset({"sample_id": "S1"})

    def test_registered_key_builds_typed(self):
        asset = build_asset(
            {"asset": "alignment", "sample_id": "S1", "duplicates_marked": "true"},
            path=Path("/tmp/x.bam"),
        )
        assert type(asset) is Alignment
        assert asset.sample_id == "S1"
        assert asset.duplicates_marked is True
        assert asset.path == Path("/tmp/x.bam")

    def test_registered_key_unknown_field_raises(self):
        with pytest.raises(ValueError, match="Unknown keys"):
            build_asset({"asset": "alignment", "flowcell": "X"})

    def test_registered_key_malformed_value_raises(self):
        """Strict at upload: a non-str field that doesn't json-parse is a
        hard error here, unlike specialize() which degrades at query time."""
        with pytest.raises(ValueError):
            build_asset({"asset": "alignment", "duplicates_marked": "yes"})

    def test_unregistered_key_builds_bare(self):
        kv = {"asset": "never_registered_key", "sequencer": "novaseq"}
        asset = build_asset(kv, path=Path("/tmp/sheet.tsv"))
        assert type(asset) is Asset
        assert asset.keyvalues == kv
        assert asset.path == Path("/tmp/sheet.tsv")

    def test_underscore_key_rejected_for_unregistered(self):
        with pytest.raises(ValueError, match="stamped automatically"):
            build_asset({"asset": "never_registered_key", "_owner": "me"})

    def test_underscore_key_rejected_for_registered(self):
        with pytest.raises(ValueError, match="stamped automatically"):
            build_asset({"asset": "alignment", "_owner": "me"})


class TestOwnerStamp:
    """_stamp_owner injects _owner from STARGAZER_OWNER. Env wins."""

    def test_env_set_stamps(self, monkeypatch):
        monkeypatch.setenv("STARGAZER_OWNER", "pryce")
        assert _stamp_owner({"asset": "r1"}) == {"asset": "r1", "_owner": "pryce"}

    def test_env_wins_over_existing(self, monkeypatch):
        """A rehydrated record must not carry a stale owner onto re-upload."""
        monkeypatch.setenv("STARGAZER_OWNER", "pryce")
        assert _stamp_owner({"_owner": "stale"})["_owner"] == "pryce"

    def test_env_unset_passes_through(self, monkeypatch):
        """No env, no opinion: manual attribution in scripts stays possible."""
        monkeypatch.delenv("STARGAZER_OWNER", raising=False)
        kv = {"asset": "r1", "_owner": "manual"}
        assert _stamp_owner(dict(kv)) == kv


class TestEnvPropagation:
    """Task pods stamp pipeline outputs only if the submitting process
    forwards STARGAZER_OWNER into the TaskEnvironment env_vars."""

    def test_owner_forwarded_when_set(self, monkeypatch):
        monkeypatch.setenv("STARGAZER_OWNER", "pryce")
        assert _stargazer_env_vars()["STARGAZER_OWNER"] == "pryce"

    def test_owner_absent_when_unset(self, monkeypatch):
        monkeypatch.delenv("STARGAZER_OWNER", raising=False)
        assert "STARGAZER_OWNER" not in _stargazer_env_vars()


class _FakeClient:
    """Records the uploaded Asset and assigns a fake cid."""

    def __init__(self):
        self.uploaded = None

    async def upload(self, comp):
        self.uploaded = comp
        comp.cid = "fake_cid"


class TestUploadFileTool:
    """server.py::upload_file delegates validation to build_asset()."""

    @pytest.fixture
    def fake_client(self, monkeypatch):
        from stargazer import server

        fake = _FakeClient()
        monkeypatch.setattr(server, "default_client", fake)
        return fake

    async def test_unregistered_key_uploads_as_generic_with_note(
        self, fake_client, tmp_path
    ):
        from stargazer.server import upload_file

        f = tmp_path / "sheet.tsv"
        f.write_text("a\tb\n")
        result = await upload_file(
            str(f), {"asset": "never_registered_key", "sequencer": "novaseq"}
        )
        assert "not registered" in result["note"]
        assert result["cid"] == "fake_cid"
        assert type(fake_client.uploaded) is Asset
        assert fake_client.uploaded.keyvalues["asset"] == "never_registered_key"

    async def test_registered_key_uploads_typed_without_note(
        self, fake_client, tmp_path
    ):
        from stargazer.server import upload_file

        f = tmp_path / "x.bam"
        f.write_bytes(b"BAM")
        result = await upload_file(str(f), {"asset": "alignment", "sample_id": "S1"})
        assert "note" not in result
        assert type(fake_client.uploaded) is Alignment

    async def test_underscore_key_rejected(self, fake_client, tmp_path):
        from stargazer.server import upload_file

        f = tmp_path / "x.bam"
        f.write_bytes(b"BAM")
        with pytest.raises(ValueError, match="stamped automatically"):
            await upload_file(str(f), {"asset": "alignment", "_owner": "me"})
        assert fake_client.uploaded is None
