"""
### IPFS CIDs computed locally.

An asset's identity is the CID Pinata would assign it, worked out without
uploading anything. `compute_cid()` builds the same UnixFS DAG Pinata builds:
CIDv1, raw leaves, 256 KiB chunks, a balanced tree of at most 174 links per
node, sha2-256 throughout. A file that fits in one chunk is its own raw leaf
(`bafkrei…`); anything larger gets a dag-pb root (`bafybei…`).

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


def compute_cid(path: Path) -> str:
    """Return the IPFS CID Pinata assigns `path`, reading it once in chunks.

    Args:
        path: The file to hash

    Returns:
        The CIDv1 in base32 (`bafk…` for one chunk, `bafy…` otherwise)
    """
    level: list[tuple[bytes, int, int]] = []
    with Path(path).open("rb") as fh:
        while block := fh.read(CHUNK_BYTES):
            level.append((_cid(_RAW, block), len(block), len(block)))
    if not level:
        level = [(_cid(_RAW, b""), 0, 0)]
    while len(level) > 1:
        level = [
            _node(level[i : i + MAX_LINKS]) for i in range(0, len(level), MAX_LINKS)
        ]
    return "b" + base64.b32encode(level[0][0]).decode().lower().rstrip("=")
