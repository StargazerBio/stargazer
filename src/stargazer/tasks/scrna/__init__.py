"""
### scRNA-seq tasks for Stargazer.

spec: [docs/workflows/scrna.md](../workflows/scrna.md)
"""

from stargazer.tasks.scrna.qc_filter import qc_filter
from stargazer.tasks.scrna.normalize import normalize
from stargazer.tasks.scrna.select_features import select_features
from stargazer.tasks.scrna.reduce_dimensions import reduce_dimensions
from stargazer.tasks.scrna.cluster import cluster
from stargazer.tasks.scrna.find_markers import find_markers

__all__ = [
    "qc_filter",
    "normalize",
    "select_features",
    "reduce_dimensions",
    "cluster",
    "find_markers",
]
