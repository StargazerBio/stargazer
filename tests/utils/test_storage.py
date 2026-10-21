"""Tests for the storage client: object-store bytes, SQLite index, local cache."""

from pathlib import Path

import pytest
from flyte.io import File
from flyte.types import TypeEngine

import stargazer.utils.storage as storage_mod
from stargazer.assets import (
    R1,
    AlignerIndex,
    Alignment,
    Reference,
    ReferenceIndex,
    assemble,
)
from stargazer.utils.cid import compute_cid
from stargazer.utils.index import SqliteIndex
from stargazer.utils.storage import StorageClient


def _client(
    root: Path, cache: str = "cache", public=None, gateway: str | None = None
) -> StorageClient:
    """A client on a local store and index under `root`, with its own cache dir."""
    return StorageClient(
        local_dir=root / cache,
        store_root=str(root / "store"),
        index=SqliteIndex(root / "index.db"),
        public=public,
        gateway=gateway,
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
async def test_extra_keyvalue_round_trips_through_the_index(client, tmp_path):
    """A typed asset's extra key is stored, matched by assemble, and returned."""
    fq = _write(tmp_path / "work" / "s1_R1.fastq", b"@r\nACGT\n+\nIIII\n")
    r1 = R1()
    r1.keyvalues["lane"] = "3"
    await r1.update(fq, sample_id="S1")

    [found] = await assemble(asset="r1", lane="3")

    assert type(found) is R1
    assert (found.cid, found.sample_id) == (r1.cid, "S1")
    assert found.keyvalues == {"lane": "3"}


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
    await idx.update(fai, build="T", companion_of=ref.cid)

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


class _PublicCompanions:
    """A public tier whose files sit in a local gateway dir; it records each query."""

    def __init__(self, gateway: Path):
        self.gateway = gateway
        self.records = []
        self.queries = []

    def add(self, name: str, data: bytes, **keyvalues: str) -> None:
        """Publish `data` as `name`, served at <gateway>/ipfs/<cid>."""
        staged = _write(self.gateway / "staging" / name, data)
        cid = compute_cid(staged)
        staged.rename(_write(self.gateway / "ipfs" / cid, b""))
        self.records.append({"cid": cid, "name": name, "keyvalues": keyvalues})

    async def query(self, keyvalues):
        self.queries.append(dict(keyvalues))
        return [
            r
            for r in self.records
            if all(r["keyvalues"].get(k) == v for k, v in keyvalues.items())
        ]

    async def get(self, cid):
        return next((r for r in self.records if r["cid"] == cid), None)


def _listing(directory: Path) -> dict[str, bytes]:
    """Every file in `directory`, name to bytes."""
    return {p.name: p.read_bytes() for p in directory.iterdir()}


@pytest.mark.asyncio
async def test_fetch_keeps_own_companions_unmixed_with_public_ones(
    tmp_path, monkeypatch
):
    """A user with companions gets only theirs, and Pinata isn't asked.

    The public tier holds a differently built bwa index for the same
    reference: a `ref.fa.bwt` with other bytes and a `ref.fa.sa` the user
    doesn't have. Mixing them would hand bwa an index from two builds.
    """
    public = _PublicCompanions(tmp_path / "gateway")
    c = _client(tmp_path, public=public, gateway=str(public.gateway))
    monkeypatch.setattr(storage_mod, "default_client", c)
    ref = Reference()
    await ref.update(_write(tmp_path / "w" / "ref.fa", b">chr1\nACGT\n"), build="T")
    await AlignerIndex().update(
        _write(tmp_path / "w" / "ref.fa.bwt", b"my bwt"),
        aligner="bwa",
        build="T",
        companion_of=ref.cid,
    )
    public.add("ref.fa.bwt", b"public bwt", companion_of=ref.cid)
    public.add("ref.fa.sa", b"public sa", companion_of=ref.cid)

    pod = _client(tmp_path, cache="pod", public=public, gateway=str(public.gateway))
    monkeypatch.setattr(storage_mod, "default_client", pod)
    local = await ref.fetch()

    assert _listing(local.parent) == {
        "ref.fa": b">chr1\nACGT\n",
        "ref.fa.bwt": b"my bwt",
    }
    assert public.queries == []


@pytest.mark.asyncio
async def test_fetch_fills_in_public_companions_when_the_user_has_none(
    tmp_path, monkeypatch
):
    """A private copy of a public reference, with no companions of its own, gets the public ones."""
    public = _PublicCompanions(tmp_path / "gateway")
    c = _client(tmp_path, public=public, gateway=str(public.gateway))
    monkeypatch.setattr(storage_mod, "default_client", c)
    ref = Reference()
    await ref.update(_write(tmp_path / "w" / "ref.fa", b">chr1\nACGT\n"), build="T")
    public.add("ref.fa", b">chr1\nACGT\n", asset="reference", _owner="maintainer")
    public.add(
        "ref.fa.fai", b"chr1\t4\t6\t4\t5\n", companion_of=ref.cid, _owner="maintainer"
    )

    pod = _client(tmp_path, cache="pod", public=public, gateway=str(public.gateway))
    monkeypatch.setattr(storage_mod, "default_client", pod)
    local = await ref.fetch()

    assert _listing(local.parent) == {
        "ref.fa": b">chr1\nACGT\n",
        "ref.fa.fai": b"chr1\t4\t6\t4\t5\n",
    }
    assert public.queries == [{"companion_of": ref.cid}]


@pytest.mark.asyncio
async def test_public_companions_come_from_the_parents_publisher(tmp_path, monkeypatch):
    """Another publisher's index for a public reference isn't mixed in."""
    public = _PublicCompanions(tmp_path / "gateway")
    c = _client(tmp_path, public=public, gateway=str(public.gateway))
    monkeypatch.setattr(storage_mod, "default_client", c)
    ref = Reference()
    await ref.update(_write(tmp_path / "w" / "ref.fa", b">chr1\nACGT\n"), build="T")
    public.add("ref.fa", b">chr1\nACGT\n", asset="reference", _owner="maintainer")
    public.add(
        "ref.fa.bwt", b"maintainer bwt", companion_of=ref.cid, _owner="maintainer"
    )
    public.add("ref.fa.bwt", b"other bwt", companion_of=ref.cid, _owner="someone")
    public.add("ref.fa.sa", b"other sa", companion_of=ref.cid, _owner="someone")

    pod = _client(tmp_path, cache="pod", public=public, gateway=str(public.gateway))
    monkeypatch.setattr(storage_mod, "default_client", pod)
    local = await ref.fetch()

    assert _listing(local.parent) == {
        "ref.fa": b">chr1\nACGT\n",
        "ref.fa.bwt": b"maintainer bwt",
    }


@pytest.mark.asyncio
async def test_no_public_companions_without_a_public_parent(tmp_path, monkeypatch):
    """Companions of a file nobody published publicly have no publisher to follow."""
    public = _PublicCompanions(tmp_path / "gateway")
    c = _client(tmp_path, public=public, gateway=str(public.gateway))
    monkeypatch.setattr(storage_mod, "default_client", c)
    ref = Reference()
    await ref.update(_write(tmp_path / "w" / "ref.fa", b">chr1\nACGT\n"), build="T")
    public.add(
        "ref.fa.fai", b"chr1\t4\t6\t4\t5\n", companion_of=ref.cid, _owner="someone"
    )

    assert await c.companions(ref.cid) == []


@pytest.mark.asyncio
async def test_query_merges_public_tier(tmp_path, monkeypatch):
    """Public records join the user's rows by CID; the user's own row wins."""
    monkeypatch.delenv("STARGAZER_OWNER", raising=False)

    class _Public:
        """A public tier that knows one shared CID and one CID the user also has."""

        def __init__(self):
            self.shared_cid = ""

        async def query(self, keyvalues):
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


class _PublicTier:
    """A public tier that records each upload and assigns the CID Pinata would."""

    def __init__(self, cid: str = ""):
        self.uploads = []
        self.cid = cid

    async def upload(self, component, path):
        self.uploads.append(
            {
                "bytes": Path(path).read_bytes(),
                "name": Path(path).name,
                "keyvalues": component.to_keyvalues(),
            }
        )
        component.cid = self.cid or compute_cid(Path(path))


@pytest.mark.asyncio
async def test_publish_sends_the_stored_file_and_its_keyvalues(tmp_path, monkeypatch):
    """Publishing uploads the stored bytes with the row's keyvalues, same CID."""
    monkeypatch.setenv("STARGAZER_OWNER", "u1")
    public = _PublicTier()
    c = _client(tmp_path, public=public)
    monkeypatch.setattr(storage_mod, "default_client", c)
    aln = Alignment()
    await aln.update(_write(tmp_path / "w" / "s1.bam", b"BAM\x07"), sample_id="S1")
    row = await c.index.get(aln.cid)

    record = await c.publish(aln.cid)

    assert public.uploads == [
        {"bytes": b"BAM\x07", "name": "s1.bam", "keyvalues": row["keyvalues"]}
    ]
    assert row["keyvalues"]["_owner"] == "u1"
    assert record == {"cid": aln.cid, "name": "s1.bam", "keyvalues": row["keyvalues"]}


@pytest.mark.asyncio
async def test_publish_refuses_without_a_public_tier(client, tmp_path):
    """No Pinata key means nothing to publish to."""
    aln = Alignment()
    await aln.update(_write(tmp_path / "w" / "s1.bam", b"BAM\x08"), sample_id="S1")

    with pytest.raises(ValueError, match="public tier"):
        await client.publish(aln.cid)


@pytest.mark.asyncio
async def test_publish_refuses_an_unknown_cid(tmp_path, monkeypatch):
    """Only the user's own stored assets can be published; nothing is sent."""
    monkeypatch.delenv("STARGAZER_OWNER", raising=False)
    public = _PublicTier()
    c = _client(tmp_path, public=public)

    with pytest.raises(ValueError, match="isn't in your storage"):
        await c.publish("bafyNotStored")
    assert public.uploads == []


@pytest.mark.asyncio
async def test_publish_raises_when_the_cid_changes(tmp_path, monkeypatch):
    """A public CID that differs from ours is a bug, not a quiet success."""
    monkeypatch.delenv("STARGAZER_OWNER", raising=False)
    c = _client(tmp_path, public=_PublicTier(cid="bafyDifferent"))
    monkeypatch.setattr(storage_mod, "default_client", c)
    aln = Alignment()
    await aln.update(_write(tmp_path / "w" / "s1.bam", b"BAM\x09"), sample_id="S1")

    with pytest.raises(ValueError, match="bafyDifferent"):
        await c.publish(aln.cid)


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
