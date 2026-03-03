"""
Constellation: dynamic query-result namespace for Stargazer assets.

A Constellation is assembled from a storage query. Assets are grouped by
_asset_key. Single matches return the asset directly; multiple matches return
a list; missing assets return None.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stargazer.types.asset import Asset


@dataclass
class Constellation:
    """Dynamic namespace of assets assembled from a storage query.

    Attributes are accessed by asset_key (e.g. .reference, .alignment).
    Single results return the asset directly; multiple results return a list.
    Missing assets return None.

    Example:
        ref = await assemble(build="GRCh38")
        ref.reference         # Reference instance
        ref.reference_index   # ReferenceIndex instance (or None)
        ref.aligner_index     # list[AlignerIndex] (or None)
    """

    _assets: dict[str, "Asset | list[Asset]"] = field(default_factory=dict)

    def __getattr__(self, name: str) -> "Asset | list[Asset] | None":
        # Only called when normal attribute lookup fails.
        # Guard against recursion before _assets is set in __init__.
        assets = self.__dict__.get("_assets", {})
        return assets.get(name)

    async def fetch(self) -> Path:
        """Download all contained assets to local cache.

        Returns:
            The local cache directory path.

        Raises:
            ValueError: If the Constellation is empty.
        """
        import stargazer.utils.storage as _storage

        all_assets: list[Asset] = []
        for value in self._assets.values():
            if isinstance(value, list):
                all_assets.extend(value)
            elif value is not None:
                all_assets.append(value)

        if not all_assets:
            raise ValueError("No assets to fetch. Constellation is empty.")

        for a in all_assets:
            await _storage.default_client.download(a)

        return _storage.default_client.local_dir


async def assemble(**filters: Any) -> Constellation:
    """Query storage by keyvalue filters, specialize results, return as Constellation.

    Wraps the cartesian product query + specialize pattern into a single call.
    Workflows call this at the top to gather what they need.

    The `asset` filter key accepts a string or list of strings to narrow by asset type.
    Other filters are passed through as keyvalue matchers.

    Args:
        **filters: Keyvalue filters. Values may be scalars or lists (cartesian product).

    Returns:
        Constellation namespace with assets grouped by _asset_key.

    Examples:
        ref = await assemble(build="GRCh38")
        ref.reference        # Reference instance
        ref.reference_index  # ReferenceIndex instance

        reads = await assemble(sample_id="NA12878", asset=["r1", "r2"])
        reads.r1             # R1 instance
        reads.r2             # R2 instance
    """
    import stargazer.utils.storage as _storage
    from stargazer.types import specialize
    from stargazer.utils.query import generate_query_combinations

    query_combinations = generate_query_combinations(base_query={}, filters=filters)

    # Execute queries, deduplicate by CID
    all_assets: dict[str, Asset] = {}
    for query in query_combinations:
        for raw in await _storage.default_client.query(query):
            all_assets[raw.cid] = raw

    # Specialize and group by _asset_key
    grouped: dict[str, list[Asset]] = {}
    for asset in all_assets.values():
        specialized = specialize(asset)
        key = specialized._asset_key or specialized.keyvalues.get("asset", "")
        if key:
            grouped.setdefault(key, []).append(specialized)

    # Collapse single-item lists to scalars
    namespace: dict[str, Asset | list[Asset]] = {
        k: (v[0] if len(v) == 1 else v) for k, v in grouped.items()
    }
    return Constellation(_assets=namespace)
