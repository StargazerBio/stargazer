"""The index tests, run against the real Aurora DSQL cluster.

`test_read_during_a_held_write` stays with SQLite: it holds SQLite's file lock.
`test_concurrent_merges_keep_every_key` writes one row from many connections
at once, which DSQL refuses all but one of at commit, so it passes only
through the write retry.
"""

from utils.test_index import (  # noqa: F401 — pytest collects the imported tests
    test_companion_lookup,
    test_concurrent_merges_keep_every_key,
    test_delete_is_idempotent,
    test_exact_match,
    test_list_filter_matches_any,
    test_merge_missing_row_raises,
    test_new_metadata_replaces_and_warns,
    test_round_trip,
    test_same_row_twice_is_one_row_without_warning,
    warnings,
)
