"""
### Query generation utilities for Stargazer.

Expands list-valued filters into one exact-match query per combination, for
backends that can't match a list in one query (Pinata's keyvalue filters).

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from itertools import product
from typing import Any


def generate_query_combinations(
    base_query: dict[str, Any],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Generate query combinations from filters using cartesian product.

    Takes a base query dict and filters dict, where filters can contain
    scalar values or lists. For any list-valued filter, generates all
    combinations using cartesian product, while preserving scalar filters
    and the base query in all combinations.

    Args:
        base_query: Base query dict to include in all combinations
        filters: Filter dict with scalar or list values

    Returns:
        List of query dicts representing all combinations

    Example:
        >>> base = {"asset": "reference"}
        >>> filters = {"build": "GRCh38", "tool": ["samtools_faidx", "gatk"]}
        >>> generate_query_combinations(base, filters)
        [
            {"asset": "reference", "build": "GRCh38", "tool": "samtools_faidx"},
            {"asset": "reference", "build": "GRCh38", "tool": "gatk"}
        ]

        >>> base = {}
        >>> filters = {"asset": ["r1", "r2"], "sample_id": ["S1", "S2"]}
        >>> generate_query_combinations(base, filters)
        [
            {"asset": "r1", "sample_id": "S1"},
            {"asset": "r1", "sample_id": "S2"},
            {"asset": "r2", "sample_id": "S1"},
            {"asset": "r2", "sample_id": "S2"}
        ]
    """
    list_filters = {}
    scalar_filters = {}

    for key, value in filters.items():
        if isinstance(value, list):
            list_filters[key] = value
        else:
            scalar_filters[key] = value

    if list_filters:
        keys = list(list_filters.keys())
        value_lists = [list_filters[k] for k in keys]

        query_combinations = []
        for combo in product(*value_lists):
            query = {**base_query, **scalar_filters}
            query.update(dict(zip(keys, combo)))
            query_combinations.append(query)
    else:
        query_combinations = [{**base_query, **scalar_filters}]

    return query_combinations
