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

    A companion: `companion_of` is the CID of the Variants file it indexes.
    """

    _asset_key: ClassVar[str] = "variants_index"
    sample_id: str = ""
    companion_of: str = ""


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

    A companion: `companion_of` is the CID of the KnownSites VCF it indexes.
    """

    _asset_key: ClassVar[str] = "known_sites_index"
    companion_of: str = ""


@dataclass
class VQSRModel(Asset):
    """VQSR recalibration model: the .recal file VariantRecalibrator writes.

    ApplyVQSR needs two more files from the same run, stored as its
    companions: the recal file's index (`VQSRModelIndex`) and the tranches
    file (`VQSRTranches`).
    """

    _asset_key: ClassVar[str] = "vqsr_model"
    sample_id: str = ""
    mode: str = "SNP"
    build: str = ""
    variants_cid: str = ""


@dataclass
class VQSRModelIndex(Asset):
    """VCF index (.idx) for a VQSRModel's recal file.

    A companion: `companion_of` is the CID of the VQSRModel it indexes.
    """

    _asset_key: ClassVar[str] = "vqsr_model_index"
    sample_id: str = ""
    companion_of: str = ""


@dataclass
class VQSRTranches(Asset):
    """VQSR tranches file: the VQSLOD cutoff for each truth-sensitivity level.

    A companion: `companion_of` is the CID of the VQSRModel it was built
    with.
    """

    _asset_key: ClassVar[str] = "vqsr_tranches"
    sample_id: str = ""
    companion_of: str = ""
