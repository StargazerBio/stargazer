"""Tests for the storage client: object-store bytes, SQLite index, local cache."""

from pathlib import Path

import pytest
from flyte.io import File
from flyte.types import TypeEngine

import stargazer.utils.storage as storage_mod
from stargazer.assets import Alignment, Reference, ReferenceIndex
from stargazer.utils.cid import compute_cid
from stargazer.utils.index import SqliteIndex
from stargazer.utils.storage import StorageClient


def _client(root: Path, cache: str = "cache", public=None) -> StorageClient:
    """A client on a local store and index under `root`, with its own cache dir."""
    return StorageClient(
        local_dir=root / cache,
        store_root=str(root / "store"),
        index=SqliteIndex(root / "index.db"),
        public=public,
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The default client, pointed at a temp store, index and cache."""
    monkeypatch.delenv("STARGAZER_OWNER", raising=False)
    c = _client(tmp_path)
    monkeypatch.setattr(storage_mod, "default_client", c)
    return c


def _write(path: Path, data: bytes) -> Path:
    """Write bytes to a fresh file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.mark.asyncio
async def test_upload_stores_by_cid_and_indexes(client, tmp_path):
    """Bytes land at users/local/assets/<cid>/<name>; the asset gets a File and a row."""
    bam = _write(tmp_path / "work" / "s1.bam", b"BAM\x01")
    cid = compute_cid(bam)

    aln = Alignment()
    await aln.update(bam, sample_id="S1")

    uri = f"{tmp_path}/store/users/local/assets/{cid}/s1.bam"
    assert aln.cid == cid
    assert isinstance(aln.path, File)
    assert (aln.path.path, aln.path.name, aln.path.hash) == (uri, "s1.bam", cid)
    assert Path(uri).read_bytes() == b"BAM\x01"
    [row] = await client.index.query({"asset": "alignment", "sample_id": "S1"})
    assert (row["cid"], row["uri"], row["name"]) == (cid, uri, "s1.bam")


@pytest.mark.asyncio
async def test_upload_stamps_owner(client, tmp_path, monkeypatch):
    """STARGAZER_OWNER names the user folder and is stamped as `_owner`."""
    monkeypatch.setenv("STARGAZER_OWNER", "387300641116005877")
    bam = _write(tmp_path / "work" / "s1.bam", b"BAM\x02")

    aln = Alignment()
    await aln.update(bam, sample_id="S1")

    assert "/users/387300641116005877/assets/" in aln.path.path
    [row] = await client.index.query({"asset": "alignment"})
    assert row["keyvalues"]["_owner"] == "387300641116005877"


@pytest.mark.asyncio
async def test_fetch_downloads_into_cid_dir_with_real_name(
    client, tmp_path, monkeypatch
):
    """A fresh cache downloads to <local_dir>/<cid>/<name> and returns that path."""
    bam = _write(tmp_path / "work" / "s1.bam", b"BAM\x03")
    aln = Alignment()
    await aln.update(bam, sample_id="S1")

    fresh = _client(tmp_path, cache="fresh_cache")
    monkeypatch.setattr(storage_mod, "default_client", fresh)
    local = await aln.fetch()

    assert local == tmp_path / "fresh_cache" / aln.cid / "s1.bam"
    assert local.read_bytes() == b"BAM\x03"


@pytest.mark.asyncio
async def test_fetch_is_a_cache_hit_after_upload(client, tmp_path):
    """An upload seeds the cache, so fetch doesn't need the store."""
    bam = _write(tmp_path / "work" / "s1.bam", b"BAM\x04")
    aln = Alignment()
    await aln.update(bam, sample_id="S1")
    Path(aln.path.path).unlink()

    local = await aln.fetch()

    assert local.read_bytes() == b"BAM\x04"


@pytest.mark.asyncio
async def test_fetch_colocates_companions(client, tmp_path, monkeypatch):
    """Companions land next to the asset, where tools look for them."""
    fa = _write(tmp_path / "work" / "ref.fa", b">chr1\nACGT\n")
    fai = _write(tmp_path / "work" / "ref.fa.fai", b"chr1\t4\t6\t4\t5\n")
    ref = Reference()
    await ref.update(fa, build="T")
    idx = ReferenceIndex()
    await idx.update(fai, build="T", reference_cid=ref.cid)

    monkeypatch.setattr(storage_mod, "default_client", _client(tmp_path, cache="c2"))
    local = await ref.fetch()

    assert (local.parent / "ref.fa.fai").read_bytes() == b"chr1\t4\t6\t4\t5\n"


@pytest.mark.asyncio
async def test_fetch_returns_an_unstored_local_file_as_is(client, tmp_path):
    """An asset built from a local file that was never uploaded is used in place."""
    fa = _write(tmp_path / "loose" / "ref.fa", b">chr1\nA\n")

    local = await Reference(path=fa, build="T").fetch()

    assert local == fa


@pytest.mark.asyncio
async def test_fetch_resolves_a_bare_cid_through_the_index(
    client, tmp_path, monkeypatch
):
    """An asset with only a CID finds its file through the index."""
    aln = Alignment()
    await aln.update(_write(tmp_path / "w" / "s1.bam", b"BAM\x07"), sample_id="S1")

    monkeypatch.setattr(storage_mod, "default_client", _client(tmp_path, cache="c3"))
    local = await Alignment(cid=aln.cid).fetch()

    assert local.name == "s1.bam"
    assert local.read_bytes() == b"BAM\x07"


@pytest.mark.asyncio
async def test_query_merges_public_tier(tmp_path, monkeypatch):
    """Public records join the user's rows by CID; the user's own row wins."""
    monkeypatch.delenv("STARGAZER_OWNER", raising=False)

    class _Public:
        """A public tier that knows one shared CID and one CID the user also has."""

        def __init__(self):
            self.shared_cid = ""

        async def query(self, keyvalues, network=None):
            assert network == "public"
            return [
                {
                    "cid": "bafyPublic",
                    "name": "pub.fa",
                    "keyvalues": {"asset": "reference"},
                },
                {
                    "cid": self.shared_cid,
                    "name": "x.fa",
                    "keyvalues": {"asset": "reference", "who": "public"},
                },
            ]

    public = _Public()
    c = _client(tmp_path, public=public)
    monkeypatch.setattr(storage_mod, "default_client", c)
    ref = Reference()
    await ref.update(_write(tmp_path / "w" / "x.fa", b">x\n"), build="T")
    public.shared_cid = ref.cid

    rows = {r["cid"]: r for r in await c.query({"asset": "reference"})}

    assert set(rows) == {ref.cid, "bafyPublic"}
    assert rows[ref.cid]["uri"] == ref.path.path
    assert rows["bafyPublic"]["uri"].endswith("/ipfs/bafyPublic")


@pytest.mark.asyncio
async def test_delete_removes_row_and_bytes(client, tmp_path):
    """Delete drops the index row and the stored file."""
    aln = Alignment()
    await aln.update(_write(tmp_path / "w" / "s1.bam", b"BAM\x05"), sample_id="S1")
    stored = Path(aln.path.path)

    await client.delete(aln)

    assert await client.index.get(aln.cid) is None
    assert not stored.exists()


@pytest.mark.asyncio
async def test_update_metadata_merges_and_stamps_owner(client, tmp_path, monkeypatch):
    """A metadata patch merges onto the row and restamps `_owner`."""
    aln = Alignment()
    await aln.update(_write(tmp_path / "w" / "s1.bam", b"BAM\x06"), sample_id="S1")
    monkeypatch.setenv("STARGAZER_OWNER", "u1")

    row = await client.update_metadata(aln.cid, {"tool": "bwa"})

    assert row["keyvalues"]["tool"] == "bwa"
    assert row["keyvalues"]["sample_id"] == "S1"
    assert row["keyvalues"]["_owner"] == "u1"


def test_local_path_becomes_a_file(tmp_path):
    """Assigning a Path to `path` stores a File pointing at it, named after it."""
    ref = Reference(path=tmp_path / "ref.fa")

    assert isinstance(ref.path, File)
    assert (ref.path.path, ref.path.name) == (str(tmp_path / "ref.fa"), "ref.fa")


@pytest.mark.asyncio
async def test_asset_with_file_round_trips_through_flyte():
    """A typed asset holding a File survives Flyte's type engine."""
    aln = Alignment(
        cid="bafyA",
        path=File(
            path="s3://bucket/users/u/assets/bafyA/s1.bam", name="s1.bam", hash="bafyA"
        ),
        sample_id="S1",
        duplicates_marked=True,
    )
    lt = TypeEngine.to_literal_type(Alignment)
    back = await TypeEngine.to_python_value(
        await TypeEngine.to_literal(aln, Alignment, lt), Alignment
    )

    assert back.cid == "bafyA"
    assert (back.path.path, back.path.hash) == (
        "s3://bucket/users/u/assets/bafyA/s1.bam",
        "bafyA",
    )
    assert (back.sample_id, back.duplicates_marked) == ("S1", True)
