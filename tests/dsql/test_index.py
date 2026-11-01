"""The index contract (tests/utils/test_index.py), on the real Aurora DSQL cluster.

`test_read_during_a_held_write` stays with SQLite: it holds SQLite's file lock.
`test_concurrent_merges_keep_every_key` writes one row from many connections
at once, which DSQL refuses all but one of at commit, so it passes only
through the write retry.
"""

from utils.test_index import TestIndexContract  # noqa: F401 — pytest collects it
