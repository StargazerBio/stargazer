"""Tests for locally computed IPFS CIDs."""

import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.utils.cid import compute_cid


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
