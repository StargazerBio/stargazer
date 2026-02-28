"""
Variants types for Stargazer.

Defines ComponentFile subclasses for VCF/GVCF variant call files and the
Variants container that composes them.
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.component import ComponentFile
from stargazer.types.biotype import BioType


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class VariantsFile(ComponentFile):
    """VCF/GVCF variant call file component."""

    _type_key: ClassVar[str] = "variants"
    _component_key: ClassVar[str] = "vcf"
    _field_types = {"sample_count": int, "source_samples": list}
    _field_defaults = {"sample_id": ""}


@dataclass
class VariantsIndex(ComponentFile):
    """VCF index (.tbi) file component."""

    _type_key: ClassVar[str] = "variants"
    _component_key: ClassVar[str] = "index"
    _field_defaults = {"sample_id": ""}


# ---------------------------------------------------------------------------
# BioType
# ---------------------------------------------------------------------------


@dataclass
class Variants(BioType):
    """
    Variant calls in VCF/GVCF format stored as typed component files.

    Attributes:
        sample_id: Sample identifier
        vcf: VCF/GVCF file
        index: VCF index (.tbi) file
    """

    sample_id: str
    vcf: VariantsFile | None = None
    index: VariantsIndex | None = None
