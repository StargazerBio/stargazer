"""
Reference genome asset types for Stargazer.
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.asset import Asset


@dataclass
class Reference(Asset):
    """Reference FASTA file asset."""

    _asset_key: ClassVar[str] = "reference"
    _field_defaults = {"build": ""}


@dataclass
class ReferenceIndex(Asset):
    """FASTA index (.fai) file asset.

    Carries reference_cid linking back to the Reference it was built from.
    """

    _asset_key: ClassVar[str] = "reference_index"
    _field_defaults = {"build": ""}


@dataclass
class SequenceDict(Asset):
    """Sequence dictionary (.dict) file asset."""

    _asset_key: ClassVar[str] = "sequence_dict"
    _field_defaults = {"build": ""}


@dataclass
class AlignerIndex(Asset):
    """Aligner index file asset (one file per index file for multi-file indices)."""

    _asset_key: ClassVar[str] = "aligner_index"
    _field_defaults = {"build": "", "aligner": ""}
