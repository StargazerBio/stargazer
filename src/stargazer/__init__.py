"""
### Stargazer: bioinformatics workflow orchestration on Flyte v2.

Every file is a typed asset identified by its IPFS CID, computed locally
from the bytes. The bytes live in an object store, the metadata in a
queryable index, and shared public data on Pinata's public network; tasks
find their inputs by querying that metadata rather than by path.

The root holds what a notebook or workflow imports: the `Asset` base and
every asset type, `assemble()`, `fetch_bundle()` and `init_flyte()`. The
storage clients are in `stargazer.utils`. The notebook controls
`run_location()` and `dispatch()` are in `stargazer.notebooks.ui`, since they
import marimo and the package doesn't depend on it.

spec: [docs/architecture/overview.md](../architecture/overview.md)
"""

from importlib.metadata import version

__version__ = version("stargazer-bio")

from stargazer.assets import (
    R1,
    R2,
    AlignerIndex,
    Alignment,
    AlignmentIndex,
    AnnData,
    Asset,
    BQSRReport,
    DuplicateMetrics,
    KnownSites,
    KnownSitesIndex,
    Notebook,
    Reference,
    ReferenceIndex,
    SequenceDict,
    Variants,
    VariantsIndex,
    VQSRModel,
    VQSRModelIndex,
    VQSRTranches,
    assemble,
)
from stargazer.bundles import fetch_bundle
from stargazer.config import init_flyte

__all__ = [
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
    "__version__",
    "assemble",
    "fetch_bundle",
    "init_flyte",
]
