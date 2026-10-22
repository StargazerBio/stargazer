"""
Unit tests for query generation utilities.
"""

from stargazer.utils.query import generate_query_combinations


def test_scalar_filters_make_one_query():
    """Scalar-only filters are a single query, as given."""
    filters = {"build": "GRCh38", "format": "fasta"}

    assert generate_query_combinations(filters) == [filters]


def test_no_filters_make_one_empty_query():
    """No filters is one query that matches everything."""
    assert generate_query_combinations({}) == [{}]


def test_a_list_filter_expands_beside_the_scalars():
    """Each entry of a list gets its own query, with every scalar filter in it."""
    filters = {"build": "GRCh38", "tool": ["fasta", "bwa", "faidx"]}

    assert generate_query_combinations(filters) == [
        {"build": "GRCh38", "tool": "fasta"},
        {"build": "GRCh38", "tool": "bwa"},
        {"build": "GRCh38", "tool": "faidx"},
    ]


def test_list_filters_take_the_cartesian_product():
    """Several list filters yield every combination of their entries."""
    filters = {"build": ["GRCh38", "GRCh37"], "tool": ["fasta", "bwa"]}

    assert generate_query_combinations(filters) == [
        {"build": "GRCh38", "tool": "fasta"},
        {"build": "GRCh38", "tool": "bwa"},
        {"build": "GRCh37", "tool": "fasta"},
        {"build": "GRCh37", "tool": "bwa"},
    ]


def test_an_empty_list_matches_nothing():
    """An empty list filter yields no queries at all."""
    assert generate_query_combinations({"build": "GRCh38", "tool": []}) == []
