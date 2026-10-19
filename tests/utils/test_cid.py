"""Tests for locally computed IPFS CIDs.

Expected CIDs come from outside this code: the fixtures' from Pinata itself
(variant_calling_demo.yaml), the deeper trees' from kubo 0.43.1 with
Pinata's parameters (`ipfs add -n --cid-version=1 --raw-leaves
--chunker=size-<n> --max-file-links=174`).

tests/pinata/test_cid_drift.py checks for drift against Pinata itself.
"""

import hashlib

import pytest
from conftest import GENERAL_FIXTURES_DIR

import stargazer.utils.cid as cid_module
from stargazer.utils.cid import CidBuilder, compute_cid

# 175 chunks of 256 KiB: one more than a single node can link.
ONE_PAST_A_NODE = 174 * 256 * 1024 + 1
# Piece sizes the builder is fed in: a byte at a time, a prime that never
# lines up with a leaf, and the chunk size of a resumable upload.
PRIME_BYTES = 7919
UPLOAD_CHUNK_BYTES = 48 * 1024**2


def _streamed(path, piece: int) -> str:
    """The builder's CID for `path`, fed `piece` bytes at a time."""
    builder = CidBuilder()
    with path.open("rb") as fh:
        while data := fh.read(piece):
            builder.update(data)
    return builder.cid()


@pytest.fixture(scope="module")
def past_one_node(tmp_path_factory):
    """A file of ONE_PAST_A_NODE deterministic, incompressible bytes."""
    blocks = -(-ONE_PAST_A_NODE // 32)
    data = b"".join(
        hashlib.sha256(i.to_bytes(8, "big")).digest() for i in range(blocks)
    )
    path = tmp_path_factory.mktemp("cid") / "past_one_node.bin"
    path.write_bytes(data[:ONE_PAST_A_NODE])
    return path


@pytest.mark.parametrize(
    ("name", "cid"),
    [
        # One block: the CID is the raw leaf itself.
        (
            "GRCh38_TP53.fa",
            "bafkreib6vj3os7l4lqqytaw5vju46iorcknttfiwfnlbizjcqn7xd5hrvy",
        ),
        # Three chunks under one UnixFS node.
        (
            "NA12829_TP53_R1.fq.gz",
            "bafybeia3lsmhibzqk3uo5phryz4wurlj26pn74klczwbmnxq3pf5q3iyy4",
        ),
        (
            "NA12829_TP53_R2.fq.gz",
            "bafybeihd3nqlci7mlotdbbxrstxchesmafsytcsltaa2jdfgppeawh3cui",
        ),
    ],
)
def test_cid_matches_pinata(name, cid):
    """A fixture hashes to the CID Pinata assigned it (variant_calling_demo.yaml)."""
    assert compute_cid(GENERAL_FIXTURES_DIR / name) == cid


def test_empty_file_is_the_zero_byte_raw_leaf(tmp_path):
    """An empty file is a single empty raw block."""
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    assert (
        compute_cid(empty)
        == "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
    )


def test_two_levels_when_chunks_overflow_one_node(past_one_node):
    """175 chunks need a second level: two nodes under a root (kubo agrees)."""
    assert (
        compute_cid(past_one_node)
        == "bafybeibwfjx4gjco2cvbbqlhbtazzttn73bsxnan2t4zmxrjmolwknbe7y"
    )


def test_three_levels(past_one_node, monkeypatch):
    """With 1 KiB chunks the same file is 44,545 leaves, past 174², so a third
    level builds: the shape a file over ~7.4 GiB gets at 256 KiB (kubo agrees).
    """
    monkeypatch.setattr(cid_module, "CHUNK_BYTES", 1024)
    assert (
        compute_cid(past_one_node)
        == "bafybeig6kus6wi5thzxnl2qb3fjfkmozg5yxdyfgq2u6p2lwed36onhlgm"
    )


@pytest.mark.parametrize("piece", [1, PRIME_BYTES, UPLOAD_CHUNK_BYTES])
@pytest.mark.parametrize(
    ("name", "cid"),
    [
        (
            "GRCh38_TP53.fa",
            "bafkreib6vj3os7l4lqqytaw5vju46iorcknttfiwfnlbizjcqn7xd5hrvy",
        ),
        (
            "NA12829_TP53_R1.fq.gz",
            "bafybeia3lsmhibzqk3uo5phryz4wurlj26pn74klczwbmnxq3pf5q3iyy4",
        ),
    ],
)
def test_builder_matches_pinata_however_the_bytes_arrive(name, cid, piece):
    """One leaf, and one node over three: the same CID in any piece size."""
    assert _streamed(GENERAL_FIXTURES_DIR / name, piece) == cid


def test_builder_with_no_bytes_is_the_zero_byte_raw_leaf():
    """Nothing fed, or only empty pieces: the empty file's CID."""
    fed_empty = CidBuilder()
    fed_empty.update(b"")
    expected = "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
    assert CidBuilder().cid() == expected
    assert fed_empty.cid() == expected


@pytest.mark.parametrize("piece", [PRIME_BYTES, UPLOAD_CHUNK_BYTES])
def test_builder_two_levels(past_one_node, piece):
    """175 leaves fed unevenly still build two nodes under a root."""
    assert (
        _streamed(past_one_node, piece)
        == "bafybeibwfjx4gjco2cvbbqlhbtazzttn73bsxnan2t4zmxrjmolwknbe7y"
    )


def test_builder_three_levels(past_one_node, monkeypatch):
    """44,545 one-KiB leaves fed in prime-sized pieces build the third level."""
    monkeypatch.setattr(cid_module, "CHUNK_BYTES", 1024)
    assert (
        _streamed(past_one_node, PRIME_BYTES)
        == "bafybeig6kus6wi5thzxnl2qb3fjfkmozg5yxdyfgq2u6p2lwed36onhlgm"
    )
