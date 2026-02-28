"""
Alignment types for Stargazer.

Defines ComponentFile subclasses for BAM/CRAM alignment files and the
Alignment container that composes them.
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.component import ComponentFile
from stargazer.types.biotype import BioType


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class AlignmentFile(ComponentFile):
    """BAM/CRAM alignment file component."""

    _type_key: ClassVar[str] = "alignment"
    _component_key: ClassVar[str] = "alignment"
    _field_types = {"duplicates_marked": bool, "bqsr_applied": bool}
    _field_defaults = {"sample_id": ""}


@dataclass
class AlignmentIndex(ComponentFile):
    """BAI/CRAI alignment index file component."""

    _type_key: ClassVar[str] = "alignment"
    _component_key: ClassVar[str] = "index"
    _field_defaults = {"sample_id": ""}


# ---------------------------------------------------------------------------
# BioType
# ---------------------------------------------------------------------------


@dataclass
class Alignment(BioType):
    """
    Aligned BAM/CRAM files stored as typed component files.

    Attributes:
        sample_id: Sample identifier
        alignment: BAM/CRAM alignment file
        index: BAI/CRAI index file
    """

    sample_id: str
    alignment: AlignmentFile | None = None
    index: AlignmentIndex | None = None
