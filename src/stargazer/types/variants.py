"""
Variant call asset types for Stargazer.
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.asset import Asset


@dataclass
class Variants(Asset):
    """VCF/GVCF variant call file asset."""

    _asset_key: ClassVar[str] = "variants"
    _field_types = {"sample_count": int, "source_samples": list}
    _field_defaults = {"sample_id": ""}


@dataclass
class VariantsIndex(Asset):
    """VCF index (.tbi) file asset.

    Carries variants_cid linking to the Variants file it indexes.
    """

    _asset_key: ClassVar[str] = "variants_index"
    _field_defaults = {"sample_id": ""}


@dataclass
class KnownSites(Asset):
    """Known variant sites VCF used for BQSR.

    Standalone asset — carries build and source fields, no container needed.
    """

    _asset_key: ClassVar[str] = "known_sites"
    _field_defaults = {"build": ""}
