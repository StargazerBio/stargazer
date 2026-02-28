"""
Reads types for Stargazer.

Defines ComponentFile subclasses for FASTQ read files and the
Reads container that composes them.
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.component import ComponentFile
from stargazer.types.biotype import BioType


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class R1File(ComponentFile):
    """R1 (forward) FASTQ read file component."""

    _type_key: ClassVar[str] = "reads"
    _component_key: ClassVar[str] = "r1"
    _field_defaults = {"sample_id": ""}


@dataclass
class R2File(ComponentFile):
    """R2 (reverse) FASTQ read file component."""

    _type_key: ClassVar[str] = "reads"
    _component_key: ClassVar[str] = "r2"
    _field_defaults = {"sample_id": ""}


# ---------------------------------------------------------------------------
# BioType
# ---------------------------------------------------------------------------


@dataclass
class Reads(BioType):
    """
    FASTQ reads stored as typed component files.

    Attributes:
        sample_id: Sample identifier
        r1: R1 (forward) FASTQ file
        r2: R2 (reverse) FASTQ file (None for single-end reads)
        read_group: Optional read group metadata (ID, SM, LB, PL, PU)
    """

    sample_id: str
    r1: R1File | None = None
    r2: R2File | None = None
    read_group: dict[str, str] | None = None

    @property
    def is_paired(self) -> bool:
        """Whether this is paired-end reads (has both R1 and R2)."""
        return self.r1 is not None and self.r2 is not None

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict, adding is_paired."""
        d = super().to_dict()
        d["is_paired"] = self.is_paired
        return d
