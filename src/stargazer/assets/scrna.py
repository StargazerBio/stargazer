"""
### scRNA-seq asset types for Stargazer.

spec: [docs/workflows/scrna.md](../workflows/scrna.md)
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.assets.asset import Asset


@dataclass
class AnnData(Asset):
    """AnnData (.h5ad) file asset for single-cell RNA-seq data.

    Tracks pipeline stage, cell/gene counts, and provenance through
    the scRNA-seq processing steps.
    """

    _asset_key: ClassVar[str] = "anndata"
    sample_id: str = ""
    n_obs: int = 0
    n_vars: int = 0
    stage: str = ""
    organism: str = ""
    source_cid: str = ""
