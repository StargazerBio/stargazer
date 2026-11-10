"""
### Stargazer types for bioinformatics workflows.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from stargazer.assets.alignment import (
    Alignment,
    AlignmentIndex,
    BQSRReport,
    DuplicateMetrics,
)
from stargazer.assets.asset import (
    ASSET_REGISTRY,
    Asset,
    assemble,
    build_asset,
    specialize,
)
from stargazer.assets.notebook import Notebook
from stargazer.assets.reads import R1, R2
from stargazer.assets.reference import (
    AlignerIndex,
    Reference,
    ReferenceIndex,
    SequenceDict,
)
from stargazer.assets.scrna import AnnData
from stargazer.assets.variants import (
    KnownSites,
    KnownSitesIndex,
    Variants,
    VariantsIndex,
    VQSRModel,
    VQSRModelIndex,
    VQSRTranches,
)

__all__ = [
    "ASSET_REGISTRY",
    "R1",
    "R2",
    "AlignerIndex",
    "Alignment",
    "AlignmentIndex",
    "AnnData",
    "Asset",
    "BQSRReport",
    "DuplicateMetrics",
    "KnownSites",
    "KnownSitesIndex",
    "Notebook",
    "Reference",
    "ReferenceIndex",
    "SequenceDict",
    "VQSRModel",
    "VQSRModelIndex",
    "VQSRTranches",
    "Variants",
    "VariantsIndex",
    "assemble",
    "build_asset",
    "specialize",
]
