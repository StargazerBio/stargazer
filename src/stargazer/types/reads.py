"""
# Read file asset types for Stargazer.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.asset import Asset


@dataclass
class R1(Asset):
    """R1 (forward) FASTQ read file asset.

    Carries mate_cid pointing to the paired R2 asset's CID (None for single-end).
    """

    _asset_key: ClassVar[str] = "r1"
    sample_id: str = ""
    mate_cid: str = ""
    sequencing_platform: str = ""


@dataclass
class R2(Asset):
    """R2 (reverse) FASTQ read file asset.

    Carries mate_cid pointing to the paired R1 asset's CID (None for single-end).
    """

    _asset_key: ClassVar[str] = "r2"
    sample_id: str = ""
    mate_cid: str = ""
    sequencing_platform: str = ""
