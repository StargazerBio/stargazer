"""
Reference genome types for Stargazer.

Defines ComponentFile subclasses for reference genome files and the
Reference container that composes them.
"""

from dataclasses import dataclass, field
from typing import ClassVar

from stargazer.types.component import ComponentFile
from stargazer.types.biotype import BioType


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class ReferenceFile(ComponentFile):
    """Reference FASTA file component."""

    _type_key: ClassVar[str] = "reference"
    _component_key: ClassVar[str] = "fasta"
    _field_defaults = {"build": ""}


@dataclass
class ReferenceIndex(ComponentFile):
    """FASTA index (.fai) file component."""

    _type_key: ClassVar[str] = "reference"
    _component_key: ClassVar[str] = "faidx"
    _field_defaults = {"build": ""}


@dataclass
class SequenceDict(ComponentFile):
    """Sequence dictionary (.dict) file component."""

    _type_key: ClassVar[str] = "reference"
    _component_key: ClassVar[str] = "sequence_dictionary"
    _field_defaults = {"build": ""}


@dataclass
class AlignerIndex(ComponentFile):
    """Aligner index file component (one file per index file for multi-file indices)."""

    _type_key: ClassVar[str] = "reference"
    _component_key: ClassVar[str] = "aligner_index"
    _field_defaults = {"build": "", "aligner": ""}


# ---------------------------------------------------------------------------
# BioType
# ---------------------------------------------------------------------------


@dataclass
class Reference(BioType):
    """
    A reference genome stored as typed component files.

    Attributes:
        build: Reference genome build (e.g., "GRCh38", "T2T-CHM13")
        fasta: Reference FASTA file
        faidx: FASTA index (.fai) file
        sequence_dictionary: Sequence dictionary (.dict) file
        aligner_index: Aligner index files (one per file in multi-file index)
    """

    build: str
    fasta: ReferenceFile | None = None
    faidx: ReferenceIndex | None = None
    sequence_dictionary: SequenceDict | None = None
    aligner_index: list[AlignerIndex] = field(default_factory=list)
