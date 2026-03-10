"""
# Stargazer types for bioinformatics workflows.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from stargazer.types.asset import Asset
from stargazer.types.asset import assemble
from stargazer.types.reference import (
    Reference,
    ReferenceIndex,
    SequenceDict,
    AlignerIndex,
)
from stargazer.types.reads import R1, R2
from stargazer.types.alignment import (
    Alignment,
    AlignmentIndex,
    BQSRReport,
    DuplicateMetrics,
)
from stargazer.types.variants import (
    Variants,
    VariantsIndex,
    KnownSites,
    KnownSitesIndex,
    VQSRModel,
)

# Auto-populated via Asset.__init_subclass__
ASSET_REGISTRY: dict[str, type[Asset]] = Asset._registry


def specialize(asset: Asset) -> Asset:
    """Convert a base Asset to its derived type based on the 'asset' keyvalue.

    Looks up the asset key in the registry and constructs the appropriate
    subclass, preserving cid, path, and all keyvalues. Returns the original
    instance unchanged if no matching derived type is found.
    """
    key = asset.keyvalues.get("asset", "")
    cls = ASSET_REGISTRY.get(key)
    if cls is None:
        return asset
    declared = set(cls._field_defaults) | set(cls._field_types)
    field_kwargs = {k: v for k, v in asset.keyvalues.items() if k in declared}
    return cls(cid=asset.cid, path=asset.path, **field_kwargs)


__all__ = [
    # Base
    "Asset",
    # Registry + helpers
    "ASSET_REGISTRY",
    "specialize",
    # Query
    "assemble",
    # Reference assets
    "Reference",
    "ReferenceIndex",
    "SequenceDict",
    "AlignerIndex",
    # Read assets
    "R1",
    "R2",
    # Alignment assets
    "Alignment",
    "AlignmentIndex",
    "BQSRReport",
    "DuplicateMetrics",
    # Variants assets
    "Variants",
    "VariantsIndex",
    "KnownSites",
    "KnownSitesIndex",
    "VQSRModel",
]
