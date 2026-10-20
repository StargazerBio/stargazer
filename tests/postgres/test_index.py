"""The index tests in tests/utils/test_index.py, run against Postgres.

`test_read_during_a_held_write` stays with SQLite: it holds SQLite's file lock.
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

from stargazer.utils.index import PostgresIndex
from stargazer.utils.storage import make_index


def test_make_index_picks_postgres_for_a_postgres_url(postgres_url):
    """A `postgresql://` STARGAZER_INDEX_URL gives a Postgres index."""
    assert type(make_index(postgres_url)) is PostgresIndex
