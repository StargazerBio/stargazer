"""
### IPFS CIDs computed locally.

An asset's identity is the CID Pinata would assign it, worked out without
uploading anything. `compute_cid()` builds the same UnixFS DAG Pinata builds:
CIDv1, raw leaves, 256 KiB chunks, a balanced tree of at most 174 links per
node, sha2-256 throughout. A file that fits in one chunk is its own raw leaf
(`bafkrei…`); anything larger gets a dag-pb root (`bafybei…`).
`CidBuilder` works it out from bytes as they arrive, in pieces of any size,
and `compute_cid()` is the builder fed a file.

Those parameters are part of every asset's identity. If Pinata changed its
defaults, a newly published file's CID would stop matching the one computed
here.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import base64
import hashlib
from pathlib import Path

CHUNK_BYTES = 256 * 1024
MAX_LINKS = 174

_RAW = 0x55
_DAG_PB = 0x70


def _varint(n: int) -> bytes:
    """Unsigned LEB128, as protobuf and multiformats encode integers."""
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(number: int, wire_type: int, payload: bytes | int) -> bytes:
    """One protobuf field: varint (wire type 0) or length-delimited (2)."""
    key = _varint((number << 3) | wire_type)
    if wire_type == 0:
        return key + _varint(payload)
    return key + _varint(len(payload)) + payload


def _cid(codec: int, block: bytes) -> bytes:
    """Binary CIDv1 of a block: version, codec, sha2-256 multihash."""
    return b"\x01" + _varint(codec) + b"\x12\x20" + hashlib.sha256(block).digest()


def _leaf(block: bytes | memoryview) -> tuple[bytes, int, int]:
    """A raw leaf as (cid, tsize, file size): both sizes are the block's."""
    return _cid(_RAW, block), len(block), len(block)


def _node(children: list[tuple[bytes, int, int]]) -> tuple[bytes, int, int]:
    """A UnixFS file node over its children; returns (cid, tsize, file size).

    Each child is (cid, tsize, file size). dag-pb encodes the links (field 2)
    before the data (field 1); the UnixFS data is Type=File, the total file
    size, and each child's file size.
    """
    links = b"".join(
        _field(2, 2, _field(1, 2, cid) + _field(2, 2, b"") + _field(3, 0, tsize))
        for cid, tsize, _ in children
    )
    filesize = sum(size for _, _, size in children)
    unixfs = (
        _field(1, 0, 2)
        + _field(3, 0, filesize)
        + b"".join(_field(4, 0, size) for _, _, size in children)
    )
    block = links + _field(1, 2, unixfs)
    tsize = len(block) + sum(t for _, t, _ in children)
    return _cid(_DAG_PB, block), tsize, filesize


class CidBuilder:
    """Works out a file's CID from its bytes, fed in pieces of any size.

    Each full leaf is hashed as soon as its bytes are in, so the state is the
    leaves' CIDs and sizes plus at most one partial leaf: a few megabytes for
    a 10 GB file. The tree over the leaves is built when `cid()` is asked.
    """

    def __init__(self) -> None:
        """Start with no bytes."""
        self._leaves: list[tuple[bytes, int, int]] = []
        self._partial = bytearray()

    def _add_leaf(self, block: bytes | memoryview) -> None:
        """Record one leaf's CID and size."""
        self._leaves.append(_leaf(block))

    def update(self, data: bytes) -> None:
        """Take the next piece of the file."""
        view = memoryview(data)
        if self._partial:
            take = CHUNK_BYTES - len(self._partial)
            self._partial += view[:take]
            view = view[take:]
            if len(self._partial) < CHUNK_BYTES:
                return
            self._add_leaf(self._partial)
            self._partial = bytearray()
        while len(view) >= CHUNK_BYTES:
            self._add_leaf(view[:CHUNK_BYTES])
            view = view[CHUNK_BYTES:]
        self._partial += view

    def cid(self) -> str:
        """The CID of everything fed so far.

        Returns:
            The CIDv1 in base32 (`bafk…` for one chunk, `bafy…` otherwise)
        """
        level = list(self._leaves)
        if self._partial or not level:
            level.append(_leaf(self._partial))
        while len(level) > 1:
            level = [
                _node(level[i : i + MAX_LINKS]) for i in range(0, len(level), MAX_LINKS)
            ]
        return "b" + base64.b32encode(level[0][0]).decode().lower().rstrip("=")


def compute_cid(path: Path) -> str:
    """Return the IPFS CID Pinata assigns `path`, reading it once in chunks.

    Args:
        path: The file to hash

    Returns:
        The CIDv1 in base32 (`bafk…` for one chunk, `bafy…` otherwise)
    """
    builder = CidBuilder()
    with Path(path).open("rb") as fh:
        while block := fh.read(CHUNK_BYTES):
            builder.update(block)
    return builder.cid()
