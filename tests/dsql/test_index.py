"""The index and state tests, run against the real Aurora DSQL cluster.

`test_read_during_a_held_write` stays with SQLite: it holds SQLite's file lock.
`test_concurrent_merges_keep_every_key` and the concurrent state tests write
one row from many connections at once, which DSQL refuses all but one of at
commit, so they pass only through the write retry.
"""

from unit.test_user_state import (  # noqa: F401 — pytest collects the imported tests
    test_a_set_value_reads_back,
    test_concurrent_conditional_deletes_take_it_once,
    test_concurrent_replaces_take_it_once,
    test_delete_removes_the_key,
    test_delete_with_a_value_only_takes_that_value,
    test_put_replaces_the_value,
    test_replace_only_takes_the_value_it_expects,
    test_with_prefix_takes_only_the_prefix,
)
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
