"""
### Stargazer types for bioinformatics workflows.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from stargazer.assets.asset import Asset
from stargazer.assets.asset import assemble
from stargazer.assets.reference import (
    Reference,
    ReferenceIndex,
    SequenceDict,
    AlignerIndex,
)
from stargazer.assets.reads import R1, R2
from stargazer.assets.alignment import (
    Alignment,
    AlignmentIndex,
    BQSRReport,
    DuplicateMetrics,
)
from stargazer.assets.variants import (
    Variants,
    VariantsIndex,
    KnownSites,
    KnownSitesIndex,
    VQSRModel,
)
from stargazer.assets.scrna import AnnData

# Auto-populated via Asset.__init_subclass__
ASSET_REGISTRY: dict[str, type[Asset]] = Asset._registry


def specialize(record: dict) -> Asset:
    """Construct a typed Asset subclass from a raw storage record.

    Looks up the 'asset' key in the record's keyvalues against the registry
    and returns the appropriate subclass instance. Returns a base Asset if
    no matching type is found.
    """
    kv = record.get("keyvalues", {})
    cid = record.get("cid", "")
    path = record.get("path")
    cls = ASSET_REGISTRY.get(kv.get("asset", ""))
    if cls is None:
        return Asset(cid=cid, path=path)
    return cls.from_keyvalues(kv, cid=cid, path=path)


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
    # scRNA-seq assets
    "AnnData",
]
