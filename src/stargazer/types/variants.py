"""
### Variant call asset types for Stargazer.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.asset import Asset


@dataclass
class Variants(Asset):
    """VCF/GVCF variant call file asset."""

    _asset_key: ClassVar[str] = "variants"
    sample_id: str = ""
    caller: str = ""
    variant_type: str = ""
    build: str = ""
    vqsr_mode: str = ""
    sample_count: int = 0
    source_samples: list = None


@dataclass
class VariantsIndex(Asset):
    """VCF index (.tbi) file asset.

    Carries variants_cid linking to the Variants file it indexes.
    """

    _asset_key: ClassVar[str] = "variants_index"
    sample_id: str = ""
    variants_cid: str = ""


@dataclass
class KnownSites(Asset):
    """Known variant sites VCF used for BQSR.

    Standalone asset — carries build and source fields, no container needed.
    """

    _asset_key: ClassVar[str] = "known_sites"
    build: str = ""
    resource_name: str = ""
    known: str = "false"
    training: str = "false"
    truth: str = "false"
    prior: str = "10"
    vqsr_mode: str = ""


@dataclass
class KnownSitesIndex(Asset):
    """VCF index (.idx) file for a KnownSites asset.

    Carries known_sites_cid linking to the KnownSites VCF it indexes.
    Fetched automatically alongside the VCF via Asset.fetch().
    """

    _asset_key: ClassVar[str] = "known_sites_index"
    known_sites_cid: str = ""


@dataclass
class VQSRModel(Asset):
    """VQSR recalibration model (.recal file + tranches path).

    Produced by VariantRecalibrator. The recal file is the primary path;
    the companion tranches file path is stored in keyvalues["tranches_path"].
    """

    _asset_key: ClassVar[str] = "vqsr_model"
    sample_id: str = ""
    mode: str = "SNP"
    tranches_path: str = ""
    build: str = ""
    variants_cid: str = ""
