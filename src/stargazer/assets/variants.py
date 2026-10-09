"""
### Variant call asset types for Stargazer.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.assets.asset import Asset


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
    """VCF index file asset (.idx, or .tbi for a bgzipped VCF).

    Carries variants_cid linking to the Variants file it indexes.
    """

    _asset_key: ClassVar[str] = "variants_index"
    sample_id: str = ""
    variants_cid: str = ""


@dataclass
class KnownSites(Asset):
    """Known variant sites VCF: BQSR known sites, or a VQSR training resource.

    `resource_name`, `known`, `training`, `truth` and `prior` are the VQSR
    resource arguments (`"true"`/`"false"` strings and a numeric prior).
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
    """VQSR recalibration model: the .recal file, plus where its tranches went.

    Produced by VariantRecalibrator. The recal file is the stored asset;
    `tranches_path` records where the tranches file was written in the pod
    that produced it, and the tranches file itself isn't stored.
    """

    _asset_key: ClassVar[str] = "vqsr_model"
    sample_id: str = ""
    mode: str = "SNP"
    tranches_path: str = ""
    build: str = ""
    variants_cid: str = ""
