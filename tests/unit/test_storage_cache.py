"""Outputs land in STARGAZER_LOCAL even when a Pinata remote is attached.

With a remote, upload delegates bytes + metadata to Pinata — but the file
should also be staged into ``local_dir`` so a later ``download()`` in the same
filesystem (local in-process execution of a workflow) is a cache hit instead
of a Pinata round-trip. This unifies on-pod storage: every asset's bytes live
under ``local_dir`` regardless of backend; only metadata routing differs.

spec: .opencode/plans/20_asset_manager_page.md
"""

from pathlib import Path

import pytest

from stargazer.assets.asset import Asset
from stargazer.utils.local_storage import LocalStorageClient


class _FakeRemote:
    """Minimal PinataClient stand-in: assigns an IPFS-style cid, no network."""

    visibility = "private"

    def __init__(self):
        self.uploaded: list[Path] = []

    async def upload(self, component: Asset) -> None:
        self.uploaded.append(component.path)
        component.cid = "bafyfake"

    async def download_to(self, cid: str, dest: Path) -> None:
        raise AssertionError("download_to should not be reached on a cache hit")


@pytest.fixture
def remote_client(tmp_path):
    """A LocalStorageClient with a fake remote and an isolated local_dir."""
    return LocalStorageClient(local_dir=tmp_path / "store", remote=_FakeRemote())


@pytest.mark.asyncio
async def test_remote_upload_stages_file_in_local_dir(remote_client, tmp_path):
    """A remote upload copies/links the output into local_dir by its name."""
    work = tmp_path / "work"
    work.mkdir()
    out = work / "s1.bam"
    out.write_bytes(b"BAM\x01\x02")

    asset = Asset(path=out)
    await remote_client.upload(asset)

    assert asset.cid == "bafyfake"  # remote still owns identity
    cached = remote_client.local_dir / "s1.bam"
    assert cached.exists()
    assert cached.read_bytes() == b"BAM\x01\x02"


@pytest.mark.asyncio
async def test_staged_output_is_a_download_cache_hit(remote_client, tmp_path):
    """After upload, a downstream fetch of the same name hits the staged cache.

    The output is produced in a working dir *outside* local_dir; only the
    staged copy lands under local_dir. A downstream asset resolves its path to
    local_dir/<name> (as ``specialize()`` does from a Pinata record), so the
    download must serve from that staged copy and never reach the remote (the
    fake's ``download_to`` raises if it does).
    """
    out = tmp_path / "work" / "s1.vcf"
    out.parent.mkdir()
    out.write_bytes(b"##fileformat=VCFv4.2\n")
    await remote_client.upload(Asset(path=out))

    downstream = Asset(cid="bafyfake", path=remote_client.local_dir / "s1.vcf")
    was_cached = await remote_client.download(downstream)

    assert was_cached is True
    assert downstream.path.read_bytes() == b"##fileformat=VCFv4.2\n"


@pytest.mark.asyncio
async def test_upload_in_place_when_already_in_local_dir(remote_client):
    """A file already inside local_dir is not copied onto itself."""
    in_place = remote_client.local_dir / "ref.fasta"
    remote_client.local_dir.mkdir(parents=True, exist_ok=True)
    in_place.write_bytes(b">chr1\nACGT\n")

    asset = Asset(path=in_place)
    await remote_client.upload(asset)  # must not raise (SameFileError)

    assert in_place.exists()
    assert in_place.read_bytes() == b">chr1\nACGT\n"
