"""
### Query generation utilities for Stargazer.

Expands list-valued filters into one exact-match query per combination, for
backends that can't match a list in one query (Pinata's keyvalue filters).

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from itertools import product
from typing import Any


def generate_query_combinations(filters: dict[str, Any]) -> list[dict[str, Any]]:
    """One exact-match query per combination of the filters' list values.

    Scalar filters appear in every query; an empty list matches nothing, so
    it yields no queries.

    Args:
        filters: Filter dict with scalar or list values

    Returns:
        List of query dicts representing all combinations

    Example:
        >>> generate_query_combinations({"build": "GRCh38", "tool": ["faidx", "gatk"]})
        [{"build": "GRCh38", "tool": "faidx"}, {"build": "GRCh38", "tool": "gatk"}]
    """
    keys = list(filters)
    values = [v if isinstance(v, list) else [v] for v in filters.values()]
    return [dict(zip(keys, combo)) for combo in product(*values)]
