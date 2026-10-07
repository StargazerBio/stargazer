"""Tests for locally computed IPFS CIDs.

Expected CIDs come from outside this code: the fixtures' from Pinata itself
(variant_calling_demo.yaml), the deeper trees' from kubo 0.43.1 with
Pinata's parameters (`ipfs add -n --cid-version=1 --raw-leaves
--chunker=size-<n> --max-file-links=174`).
"""

import hashlib

import pytest
from conftest import GENERAL_FIXTURES_DIR

import stargazer.utils.cid as cid_module
from stargazer.utils.cid import compute_cid

# 175 chunks of 256 KiB: one more than a single node can link.
ONE_PAST_A_NODE = 174 * 256 * 1024 + 1


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
